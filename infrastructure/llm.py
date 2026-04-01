"""LLM 客户端模块 - 集中管理所有 Agent 的 LLM 调用。

本模块提供单例 LLMClient，统一封装 LLM 调用接口，支持多模型提供商。
所有 Agent 通过 LLMClient.chat() 调用 LLM，确保配置集中管理。

配置从环境变量读取：
- LLM_API_KEY: API 密钥
- LLM_BASE_URL: API 基础地址
- LLM_MODEL: 模型名称（如 "MiniMax-M2.7"）

示例：
    client = LLMClient.get_instance()
    response = client.chat([{"role": "user", "content": "你好"}])
    print(response.content)
    print(response.usage)
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class ModelProvider(Enum):
    """支持的 LLM 模型提供商"""

    MINIMAX = "minimax"


PROVIDER_CONFIG: dict[ModelProvider, dict] = {
    ModelProvider.MINIMAX: {
        "api_key": os.getenv("LLM_API_KEY"),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.minimax.chat/v1"),
        "default_model": os.getenv("LLM_MODEL", "MiniMax-M2.7"),
    },
}


@dataclass
class LLMResponse:
    """LLM response with content and usage information.

    Attributes:
        content: The LLM's response text content.
        usage: Dictionary with token usage information containing:
            - prompt_tokens: Input token count
            - completion_tokens: Output token count
            - total_tokens: Total token count
        model: The model name used for this response.
    """

    content: str
    usage: dict
    model: str


class LLMClient:
    """Singleton LLM client for centralized LLM invocation.

    Uses the OpenAI-compatible API interface to communicate with various
    LLM providers. Configuration is read from environment variables.

    Attributes:
        model: The model name used for chat completions.
        client: The underlying OpenAI client instance.

    Example:
        client = LLMClient.get_instance()
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"}
        ]
        response = client.chat(messages)
        print(response.content)
        print(f"Tokens used: {response.usage['total_tokens']}")
    """

    _instance: Optional["LLMClient"] = None

    def __init__(
        self,
        provider: ModelProvider = ModelProvider.MINIMAX,
        model: Optional[str] = None,
    ):
        """Initialize the LLM client with provider configuration.

        Args:
            provider: The LLM provider to use (defaults to MINIMAX).
            model: Optional model name override. If not provided,
                uses the default model configured for the provider.
        """
        config = PROVIDER_CONFIG[provider]
        self.model = model or config["default_model"]
        self.client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])

    @classmethod
    def get_instance(cls) -> "LLMClient":
        """Get the singleton LLMClient instance.

        Creates the instance on first call, subsequent calls return
        the existing instance.

        Returns:
            The singleton LLMClient instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Send a chat completion request to the LLM.

        Args:
            messages: List of message dictionaries with 'role' and
                'content' keys. Typical format:
                [{"role": "system", "content": "..."},
                 {"role": "user", "content": "..."}]
            temperature: Sampling temperature for generation.
                Lower values (e.g., 0.3) produce more deterministic
                output, higher values (e.g., 0.8) produce more varied.
                Defaults to 0.3.

        Returns:
            LLMResponse with content, usage dict, and model name.
            Usage dict contains prompt_tokens, completion_tokens, total_tokens.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
        )

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=response.choices[0].message.content or "",
            usage=usage,
            model=self.model,
        )

    def chat_str(
        self,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> str:
        """Convenience method that returns only the content string.

        This method exists for backward compatibility. Use chat() directly
        when you need usage information.

        Args:
            messages: List of message dictionaries.
            temperature: Sampling temperature.

        Returns:
            The LLM's response text content only.
        """
        return self.chat(messages, temperature).content
