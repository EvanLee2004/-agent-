"""LLM 聊天仓储接口。"""

from abc import ABC, abstractmethod

from llm.llm_chat_request import LlmChatRequest
from llm.llm_response import LlmResponse


class LlmChatRepository(ABC):
    """LLM 聊天仓储接口。"""

    @abstractmethod
    def send_chat_request(self, chat_request: LlmChatRequest) -> LlmResponse:
        """发送带工具定义的聊天请求。

        Args:
            chat_request: 归一化后的 LLM 请求对象。

        Returns:
            归一化后的 LLM 响应对象。
        """
        raise NotImplementedError
