"""LLM 调用模块，支持多种模型提供商"""

import os
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class ModelProvider(Enum):
    MINIMAX = "minimax"


PROVIDER_CONFIG: dict[ModelProvider, dict] = {
    ModelProvider.MINIMAX: {
        "api_key": os.getenv("LLM_API_KEY"),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.minimax.chat/v1"),
        "default_model": os.getenv("LLM_MODEL", "MiniMax-M2.7"),
    },
}


class LLMClient:
    _instance: Optional["LLMClient"] = None

    def __init__(
        self,
        provider: ModelProvider = ModelProvider.MINIMAX,
        model: Optional[str] = None,
    ):
        config = PROVIDER_CONFIG[provider]
        self.model = model or config["default_model"]
        self.client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])

    @classmethod
    def get_instance(cls) -> "LLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
    ) -> str:
        """调用 LLM。

        Args:
            messages: 消息列表
            temperature: 温度参数

        Returns:
            LLM 返回的文本
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
