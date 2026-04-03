"""DeerFlow 角色运行时仓储实现。"""

from typing import Optional

from configuration.llm_configuration import LlmConfiguration
from conversation.deerflow_client_factory import DeerFlowClientFactory
from conversation.deerflow_runtime_assets import DeerFlowRuntimeAssets
from conversation.deerflow_runtime_assets_service import DeerFlowRuntimeAssetsService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_error import DepartmentError
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.department_runtime_context import DepartmentRuntimeContext


DEFAULT_THREAD_ID = "finance-cli-session"


class DeerFlowDepartmentRoleRuntimeRepository(DepartmentRoleRuntimeRepository):
    """基于 DeerFlow public client 驱动单个财务角色。

    该仓储只做“角色调用”这件事：按角色名获取 DeerFlow client，带线程与上下文
    执行一次 `chat()`，然后把结果包装为部门层可消费的角色响应。它不参与角色之间
    的协作决策，因此部门编排逻辑仍然收敛在 `department/`。
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
            with self._runtime_context.open_scope(
                role_name=request.role_name,
                thread_id=request.thread_id or DEFAULT_THREAD_ID,
                collaboration_depth=request.collaboration_depth,
            ):
                reply_text = client.chat(
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

    def _get_client(self, role_name: str):
        """按需获取某个角色对应的 DeerFlowClient。"""
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
