"""DeerFlow 角色运行时仓储实现。"""

from typing import Optional

from configuration.llm_configuration import LlmConfiguration
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_error import DepartmentError
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.department_runtime_context import DepartmentRuntimeContext
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.deerflow.deerflow_client_factory import DeerFlowClientFactory
from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets
from runtime.deerflow.deerflow_runtime_assets_service import DeerFlowRuntimeAssetsService


DEFAULT_THREAD_ID = "finance-cli-session"


class DeerFlowDepartmentRoleRuntimeRepository(DepartmentRoleRuntimeRepository):
    """基于 DeerFlow public client 驱动单个财务角色。

    该仓储只做"角色调用"这件事：按角色名获取 DeerFlow client，带线程与上下文
    执行一次对话，然后把结果包装为部门层可消费的角色响应。它不参与角色之间
    的协作决策，因此部门编排逻辑仍然收敛在 `department/`。

    重要设计决策：
    1. **每次 reply() 前 reset_agent()** - DeerFlow 的 system prompt（包括 date、
       memory、skills 上下文）在 agent 首次创建时生成并缓存。只有当配置 key
       （model_name/thinking_enabled/is_plan_mode/subagent_enabled/agent_name/
       available_skills）变化时才会自动重建。这意味着即使用户更新了 memory，
       同一 client 实例在下一轮对话中仍然会读到旧的 system prompt。

       根据 DeerFlow client.py 的文档：
       "The system prompt (including date, memory, and skills context) is
       generated when the internal agent is first created and cached until the
       configuration key changes. Call reset_agent() to force a refresh."

       因此我们在每次 reply() 前主动调用 reset_agent()，确保下一轮对话能看到
       最新的 memory/skills/date 上下文，同时保持 thread_id/checkpointer 语义不变。

    2. **使用 stream() 而非 chat()** - chat() 只是 stream() 的包装，只返回最后
       一段 AI 文本（intermediate segments are discarded）。DeerFlow 在一个
       turn 中可能输出多段 AI 文本（如思考过程、tool 结果后的再回复），
       直接用 chat() 会丢失中间内容。改用 stream() 并拼接所有 AI 文本段，
       为后续接入 tool trace / usage / artifacts 预留扩展点。
    """

    def __init__(
        self,
        configuration: LlmConfiguration,
        runtime_assets_service: DeerFlowRuntimeAssetsService,
        client_factory: DeerFlowClientFactory,
        runtime_context: DepartmentRuntimeContext,
        reply_text_sanitizer: ReplyTextSanitizer,
    ):
        self._configuration = configuration
        self._runtime_assets_service = runtime_assets_service
        self._client_factory = client_factory
        self._runtime_context = runtime_context
        self._reply_text_sanitizer = reply_text_sanitizer
        self._assets: Optional[DeerFlowRuntimeAssets] = None
        self._clients: dict[str, object] = {}

    def reply(self, request: DepartmentRoleRequest) -> DepartmentRoleResponse:
        """调用目标角色并返回其回复。"""
        try:
            client = self._get_client(request.role_name)
            # 重置 agent 以确保 memory/skills/date 上下文刷新。
            # 参见类文档"设计决策 1"。
            client.reset_agent()
            with self._runtime_context.open_scope(
                role_name=request.role_name,
                thread_id=request.thread_id or DEFAULT_THREAD_ID,
                collaboration_depth=request.collaboration_depth,
            ):
                # 使用 stream() 而非 chat()，确保不丢失多段 AI 输出。
                # 参见类文档"设计决策 2"。
                reply_text, execution_events = self._collect_reply_and_events(
                    client,
                    request.user_input,
                    thread_id=request.thread_id or DEFAULT_THREAD_ID,
                )
        except (ConnectionError, FileNotFoundError, OSError, RuntimeError, TimeoutError, ValueError) as error:
            raise DepartmentError(f"角色运行失败: {str(error)}") from error
        if not reply_text or not str(reply_text).strip():
            raise DepartmentError(f"角色 {request.role_name} 未返回有效回复")
        return DepartmentRoleResponse(
            role_name=request.role_name,
            reply_text=self._reply_text_sanitizer.sanitize(str(reply_text).strip()),
            collaboration_depth=request.collaboration_depth,
            execution_events=execution_events,
        )

    def _collect_reply_and_events(
        self,
        client: object,
        user_input: str,
        thread_id: str,
    ) -> tuple[str, list[ExecutionEvent]]:
        """从 DeerFlow stream() 中提取最终回复文本和执行事件。

        DeerFlow stream() 在 embedded mode 下产生完整 AIMessage 事件，而非 token delta。
        一个 turn 中可能出现多个 AI 消息（例如：中间回复 -> 工具调用 -> 最终回复）。
        chat() 故意只返回最后一个非空 AI 文本，这是正确的语义：
        用户可见的最终回复不应包含"我先查一下"这类中间话术。

        我们使用 stream() 而非 chat()，同时收集对用户有意义的执行事件：
        - AI 发起工具调用（generate_fiscal_task_prompt、task 等）
        - 工具执行结果（用于确认动作完成）
        - 最终 AI 文本回复（always 作为最后一步）

        最终 reply_text 取最后一个非空 AI 文本，与 chat() 语义对齐。
        execution_events 只包含对生成协作摘要有意义的事件，不暴露原始长文本 thinking。

        DeerFlow stream() 产生的事件类型（参见 deerflow/client.py:_serialize_message）：
        - messages-tuple (type=ai, content=...): AI 消息片段
        - messages-tuple (type=ai, tool_calls=[{name, args, id}]): AI 发起工具调用
          注意：tool_calls 项是 {"name": ..., "args": ..., "id": ...}，没有嵌套 "function" 结构
        - messages-tuple (type=tool, content=..., name=..., tool_call_id=...): 工具执行结果
          tool_call_id 字段与原始 tool_calls 项的 id 字段对应
        - values: 完整状态快照（含 artifacts）
        - end: 流结束，包含累计 usage
        """
        last_ai_text: str = ""
        execution_events: list[ExecutionEvent] = []
        # 追踪已记录的 tool_call 的 id，用于将 tool_result 与原始调用关联
        recorded_tool_call_ids: set[str] = set()

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
                        event_type = ExecutionEventType.TASK_CALL if tool_name == "task" else ExecutionEventType.TOOL_CALL
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

        return last_ai_text, execution_events

    def _get_client(self, role_name: str):
        """按需获取某个角色对应的 DeerFlowClient。

        注意：client 实例被缓存以便复用，但每次 reply() 前都会调用
        reset_agent() 来刷新 system prompt，因此缓存的是 client 实例
        本身而非过时的 agent 状态。
        """
        if role_name in self._clients:
            return self._clients[role_name]
        assets = self._get_assets()
        self._clients[role_name] = self._client_factory.create_client(assets, role_name)
        return self._clients[role_name]

    def _get_assets(self) -> DeerFlowRuntimeAssets:
        """按需准备 DeerFlow 运行时资产。"""
        if self._assets is None:
            self._assets = self._runtime_assets_service.prepare_assets(self._configuration)
        return self._assets
