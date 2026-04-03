"""DeerFlow 运行时仓储实现。"""

from typing import Optional

from configuration.llm_configuration import LlmConfiguration
from conversation.agent_runtime_repository import AgentRuntimeRepository
from conversation.agent_runtime_request import AgentRuntimeRequest
from conversation.agent_runtime_response import AgentRuntimeResponse
from conversation.deerflow_client_factory import DeerFlowClientFactory
from conversation.deerflow_runtime_error import DeerFlowRuntimeError
from conversation.deerflow_runtime_assets import DeerFlowRuntimeAssets
from conversation.deerflow_runtime_assets_service import DeerFlowRuntimeAssetsService

DEFAULT_THREAD_ID = "finance-cli-session"


class DeerFlowAgentRuntimeRepository(AgentRuntimeRepository):
    """通过 DeerFlowClient 驱动会话的运行时仓储。

    该仓储只负责三件事：
    1. 准备 DeerFlow 运行时资产；
    2. 按需创建并缓存 DeerFlow public client；
    3. 把用户输入映射到 DeerFlow 的 `chat()` 调用。

    它不负责财务规则、不负责工具执行，也不拼装 prompt。
    这些职责要么已经下沉到财务 tools，要么交给 DeerFlow 自己的 skills/runtime。
    """

    def __init__(
        self,
        configuration: LlmConfiguration,
        runtime_assets_service: DeerFlowRuntimeAssetsService,
        client_factory: DeerFlowClientFactory,
        agent_name: str = "finance-coordinator",
    ):
        self._configuration = configuration
        self._runtime_assets_service = runtime_assets_service
        self._client_factory = client_factory
        self._agent_name = agent_name
        self._assets: Optional[DeerFlowRuntimeAssets] = None
        self._client = None

    def reply(self, request: AgentRuntimeRequest) -> AgentRuntimeResponse:
        """执行一次 DeerFlow 会话。

        Args:
            request: 底层运行时请求。

        Returns:
            DeerFlow 生成的最终响应。

        Raises:
            DeerFlowRuntimeError: DeerFlow 初始化或执行失败时抛出。
        """
        try:
            client = self._get_client()
            reply_text = client.chat(
                request.user_input,
                thread_id=request.thread_id or DEFAULT_THREAD_ID,
            )
        except (
            DeerFlowRuntimeError,
            ConnectionError,
            FileNotFoundError,
            OSError,
            RuntimeError,
            TimeoutError,
            ValueError,
        ) as error:
            raise DeerFlowRuntimeError(f"DeerFlow 运行失败: {str(error)}") from error
        if not reply_text or not str(reply_text).strip():
            raise DeerFlowRuntimeError("DeerFlow 未返回有效回复")
        return AgentRuntimeResponse(reply_text=str(reply_text).strip())

    def _get_client(self):
        """按需获取 DeerFlowClient。"""
        if self._client is not None:
            return self._client
        assets = self._get_assets()
        self._client = self._client_factory.create_client(assets, self._agent_name)
        return self._client

    def _get_assets(self) -> DeerFlowRuntimeAssets:
        """按需准备 DeerFlow 运行时资产。"""
        if self._assets is not None:
            return self._assets
        self._assets = self._runtime_assets_service.prepare_assets(self._configuration)
        return self._assets
