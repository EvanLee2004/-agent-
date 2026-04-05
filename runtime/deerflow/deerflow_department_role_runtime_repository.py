"""DeerFlow 角色运行时仓储实现。"""

from typing import Optional

from configuration.llm_configuration import LlmConfiguration
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_error import DepartmentError
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import (
    DepartmentRoleRuntimeRepository,
)
from department.department_runtime_context import DepartmentRuntimeContext
from department.llm_usage import LlmUsage
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.deerflow.deerflow_invocation_runner import DeerFlowInvocationRunner
from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets
from runtime.deerflow.deerflow_runtime_assets_service import (
    DeerFlowRuntimeAssetsService,
)


DEFAULT_THREAD_ID = "finance-cli-session"


class DeerFlowDepartmentRoleRuntimeRepository(DepartmentRoleRuntimeRepository):
    """基于 DeerFlow public client 驱动单个财务角色。

    该仓储只做"角色调用"这件事：按角色名获取 DeerFlow client，带线程与上下文
    执行一次对话，然后把结果包装为部门层可消费的角色响应。它不参与角色之间
    的协作决策，因此部门编排逻辑仍然收敛在 `department/`。

    设计决策：
    1. 每次 reply() 前调用 reset_agent()：确保下一轮对话能看到最新的
       memory/skills/date 上下文，同时保持 thread_id/checkpointer 语义不变。
       DeerFlow 的 system prompt 在 agent 首次创建时生成并缓存，只有当
       配置 key 变化时才会自动重建。

    2. 使用 stream() 而非 chat()：DeerFlow 在一个 turn 中可能输出多段 AI 文本
       （如思考过程、tool 结果后的再回复），chat() 只返回最后一段，会丢失中间内容。
       stream() 为后续接入 tool trace / usage / artifacts 预留扩展点。
    """

    def __init__(
        self,
        configuration: LlmConfiguration,
        runtime_assets_service: DeerFlowRuntimeAssetsService,
        runtime_context: DepartmentRuntimeContext,
        reply_text_sanitizer: ReplyTextSanitizer,
        invocation_runner: DeerFlowInvocationRunner,
    ):
        self._configuration = configuration
        self._runtime_assets_service = runtime_assets_service
        self._runtime_context = runtime_context
        self._reply_text_sanitizer = reply_text_sanitizer
        self._invocation_runner = invocation_runner
        self._assets: Optional[DeerFlowRuntimeAssets] = None
        self._clients: dict[str, object] = {}

    def reply(self, request: DepartmentRoleRequest) -> DepartmentRoleResponse:
        """调用目标角色并返回其回复。"""
        assets = self._get_assets()
        thread_id = request.thread_id or DEFAULT_THREAD_ID

        def run_and_collect(
            client: object,
        ) -> tuple[str, list[ExecutionEvent], LlmUsage | None]:
            """在 runner 的 os.environ 隔离作用域内执行 DeerFlow 调用。

            重置 agent 以确保 memory/skills/date 上下文刷新，
            然后收集 stream() 事件生成 reply + execution_events + usage。
            """
            client.reset_agent()
            return self._collect_reply_and_events(
                client,
                request.user_input,
                thread_id=thread_id,
            )

        try:
            with self._runtime_context.open_scope(
                role_name=request.role_name,
                thread_id=thread_id,
                collaboration_depth=request.collaboration_depth,
            ):
                if request.role_name in self._clients:
                    client = self._clients[request.role_name]
                    reply_text, execution_events, usage = (
                        self._invocation_runner.run_with_isolation(
                            assets,
                            client,
                            run_and_collect,
                        )
                    )
                else:
                    _captured: dict = {}

                    def capture_and_reply(client: object):
                        _captured["client"] = client
                        return run_and_collect(client)

                    reply_text, execution_events, usage = (
                        self._invocation_runner.create_and_run_client(
                            assets,
                            request.role_name,
                            capture_and_reply,
                        )
                    )
                    self._clients[request.role_name] = _captured["client"]
        except (
            ConnectionError,
            FileNotFoundError,
            OSError,
            RuntimeError,
            TimeoutError,
            ValueError,
        ) as error:
            raise DepartmentError(f"角色运行失败: {str(error)}") from error
        if not reply_text or not str(reply_text).strip():
            raise DepartmentError(f"角色 {request.role_name} 未返回有效回复")
        return DepartmentRoleResponse(
            role_name=request.role_name,
            reply_text=self._reply_text_sanitizer.sanitize(str(reply_text).strip()),
            collaboration_depth=request.collaboration_depth,
            execution_events=execution_events,
            usage=usage,
        )

    def _collect_reply_and_events(
        self,
        client: object,
        user_input: str,
        thread_id: str,
    ) -> tuple[str, list[ExecutionEvent], LlmUsage | None]:
        """从 DeerFlow stream() 中提取最终回复文本、执行事件和 token 使用量。

        DeerFlow stream() 在 embedded mode 下产生完整 AIMessage 事件，而非 token delta。
        一个 turn 中可能出现多个 AI 消息（例如：中间回复 -> 工具调用 -> 最终回复）。
        chat() 故意只返回最后一个非空 AI 文本，这是正确的语义：
        用户可见的最终回复不应包含"我先查一下"这类中间话术。

        我们使用 stream() 而非 chat()，同时收集：
        - 对用户有意义的执行事件（TOOL_CALL / TASK_CALL / TOOL_RESULT / FINAL_REPLY）
        - 最终 AI 文本回复（最后一个非空 AI 文本）
        - LLM token 使用量（来自 end 事件，内部遥测，不暴露给用户）

        DeerFlow stream() 产生的事件类型（参见 deerflow/client.py:_serialize_message）：
        - messages-tuple (type=ai, content=...): AI 消息片段
        - messages-tuple (type=ai, tool_calls=[{name, args, id}]): AI 发起工具调用
          注意：tool_calls 项是 {"name": ..., "args": ..., "id": ...}，没有嵌套 "function" 结构
        - messages-tuple (type=tool, content=..., name=..., tool_call_id=...): 工具执行结果
          tool_call_id 字段与原始 tool_calls 项的 id 字段对应
        - values: 完整状态快照（含 artifacts），暂存用于未来扩展
        - end: 流结束，包含累计 usage

        Returns:
            三元组：(最终回复文本, 执行事件列表, LLM使用量或None)
        """
        last_ai_text: str = ""
        execution_events: list[ExecutionEvent] = []
        # 追踪已记录的 tool_call 的 id，用于将 tool_result 与原始调用关联
        recorded_tool_call_ids: set[str] = set()
        usage: LlmUsage | None = None

        for event in client.stream(user_input, thread_id=thread_id):
            # 收集最后一个非空 AI 文本作为最终回复
            if event.type == "messages-tuple" and event.data.get("type") == "ai":
                content = event.data.get("content", "")
                if content:
                    last_ai_text = content
                # 收集 AI 发起的工具调用
                # DeerFlow tool_calls 项结构: {"name": ..., "args": ..., "id": ...}
                # 不是 {"function": {"name": ..., "args": ...}} 那种 LangChain 旧格式
                tool_calls = event.data.get("tool_calls", [])
                for tc in tool_calls:
                    tool_name = tc.get("name", "")
                    tc_id = tc.get("id", "")
                    if tool_name and tc_id and tc_id not in recorded_tool_call_ids:
                        recorded_tool_call_ids.add(tc_id)
                        event_type = (
                            ExecutionEventType.TASK_CALL
                            if tool_name == "task"
                            else ExecutionEventType.TOOL_CALL
                        )
                        execution_events.append(
                            ExecutionEvent(
                                event_type=event_type,
                                tool_name=tool_name,
                                summary=f"调用 {tool_name}",
                            )
                        )
            # 收集工具执行结果
            elif event.type == "messages-tuple" and event.data.get("type") == "tool":
                tool_call_id = event.data.get("tool_call_id", "")
                tool_name = event.data.get("name", "")
                content = event.data.get("content", "")
                # tool_result 通过 tool_call_id 与原始 tool_call 的 id 字段关联
                # 生成简洁摘要：若 content 短则直接用，否则截断
                if tool_call_id in recorded_tool_call_ids:
                    if content:
                        # 工具返回内容通常是结构化文本，截断到合理长度
                        summary = content[:80] + "…" if len(content) > 80 else content
                    else:
                        summary = f"{tool_name} 执行完成"
                    execution_events.append(
                        ExecutionEvent(
                            event_type=ExecutionEventType.TOOL_RESULT,
                            tool_name=tool_name,
                            summary=summary,
                        )
                    )
            # 收集 end 事件中的 token 使用量（内部遥测）
            elif event.type == "end":
                usage_data = event.data.get("usage", {})
                if usage_data:
                    usage = LlmUsage(
                        input_tokens=usage_data.get("input_tokens", 0),
                        output_tokens=usage_data.get("output_tokens", 0),
                        total_tokens=usage_data.get("total_tokens", 0),
                    )
            # values 事件：完整状态快照（含 artifacts），未来扩展位，暂不处理

        # 策略：始终以 FINAL_REPLY 作为最后一步（即使本轮有工具调用）。
        # 这是 DeerFlow 多 agent 协作的最终结论，用户需要看到它。
        # 只有当没有任何其他事件时才用 reply_text 作为单步骤 fallback。
        if not execution_events and last_ai_text:
            # 无任何工具调用/结果时，FINAL_REPLY 是唯一的步骤
            execution_events.append(
                ExecutionEvent(
                    event_type=ExecutionEventType.FINAL_REPLY,
                    tool_name="",
                    summary=last_ai_text,
                )
            )
        elif execution_events and last_ai_text:
            # 有工具调用/结果时，在末尾追加 FINAL_REPLY
            execution_events.append(
                ExecutionEvent(
                    event_type=ExecutionEventType.FINAL_REPLY,
                    tool_name="",
                    summary=last_ai_text,
                )
            )

        return last_ai_text, execution_events, usage

    def _get_assets(self) -> DeerFlowRuntimeAssets:
        """按需准备 DeerFlow 运行时资产。"""
        if self._assets is None:
            self._assets = self._runtime_assets_service.prepare_assets(
                self._configuration
            )
        return self._assets
