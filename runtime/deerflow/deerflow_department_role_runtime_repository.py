"""DeerFlow 角色运行时仓储实现。"""

from typing import Optional

from configuration.llm_configuration import LlmConfiguration
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_error import DepartmentError
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.department_runtime_context import DepartmentRuntimeContext
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
                reply_text = self._collect_full_reply_text(
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
        )

    def _collect_full_reply_text(
        self,
        client: object,
        user_input: str,
        thread_id: str,
    ) -> str:
        """从 DeerFlow stream() 中拼接完整 AI 文本。

        DeerFlow stream() 会产生多种事件类型：
        - messages-tuple (type=ai): AI 文本片段
        - messages-tuple (type=tool): tool 调用结果
        - values: 完整状态快照
        - end: 流结束，包含累计 usage

        我们只拼接所有 type=ai 的 content 字段，保留完整的 AI 回复。
        后续可扩展：收集 tool_calls 用于 trace、收集 usage 用于计量。
        """
        full_text_parts: list[str] = []
        # 预留扩展点：未来可收集 tool_events / usage 等
        # tool_events: list[dict] = []
        # cumulative_usage: dict[str, int] = {}

        for event in client.stream(user_input, thread_id=thread_id):
            # 收集 AI 文本段
            if event.type == "messages-tuple" and event.data.get("type") == "ai":
                content = event.data.get("content", "")
                if content:
                    full_text_parts.append(content)
            # 预留：收集 tool 调用事件供未来 trace 使用
            # elif event.type == "messages-tuple" and event.data.get("type") == "tool":
            #     tool_events.append(event.data)
            # 预留：收集 end 事件中的 usage
            # elif event.type == "end":
            #     cumulative_usage = event.data.get("usage", {})

        return "".join(full_text_parts)

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
