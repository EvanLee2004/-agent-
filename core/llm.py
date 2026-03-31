"""LLM Client Module - Centralized LLM invocation across all Agents.

This module provides a singleton LLMClient that统一的 LLM 调用接口，
支持多种模型提供商。所有 Agent 通过 LLMClient.chat() 发起 LLM 调用，
确保 LLM 配置集中管理。

The client reads configuration from environment variables:
- LLM_API_KEY: API key for the LLM provider
- LLM_BASE_URL: Base URL for the LLM API endpoint
- LLM_MODEL: Model name to use (e.g., "MiniMax-M2.7")

Example:
    client = LLMClient.get_instance()
    response = client.chat([{"role": "user", "content": "Hello"}])
"""

import os
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class ModelProvider(Enum):
    """Supported LLM model providers."""

    MINIMAX = "minimax"


PROVIDER_CONFIG: dict[ModelProvider, dict] = {
    ModelProvider.MINIMAX: {
        "api_key": os.getenv("LLM_API_KEY"),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.minimax.chat/v1"),
        "default_model": os.getenv("LLM_MODEL", "MiniMax-M2.7"),
    },
}


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
    ) -> str:
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
            The LLM's response text content. Empty string if the
            model returned no content.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
