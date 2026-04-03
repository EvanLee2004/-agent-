"""会话运行时仓储接口。"""

from abc import ABC, abstractmethod

from conversation.agent_runtime_request import AgentRuntimeRequest
from conversation.agent_runtime_response import AgentRuntimeResponse


class AgentRuntimeRepository(ABC):
    """抽象底层 Agent 运行时。

    当前项目已经决定把通用 orchestration 能力交给 DeerFlow，
    因此会话服务不应再关心底层具体是哪个 agent 引擎。
    """

    @abstractmethod
    def reply(self, request: AgentRuntimeRequest) -> AgentRuntimeResponse:
        """执行一次运行时请求。

        Args:
            request: 运行时请求。

        Returns:
            运行时响应。

        Raises:
            RuntimeError: 底层运行时不可用或执行失败时抛出。
        """
