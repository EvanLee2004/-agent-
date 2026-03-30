"""LLM 调用模块，支持多种模型提供商"""

import os
from enum import Enum
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class ModelProvider(Enum):
    MINIMAX = "minimax"


PROVIDER_CONFIG: dict[ModelProvider, dict] = {
    ModelProvider.MINIMAX: {
        "api_key": os.getenv("MINIMAX_API_KEY"),
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "MiniMax-M2.7",
    },
}


class LLMClient:
    def __init__(
        self,
        provider: ModelProvider = ModelProvider.MINIMAX,
        model: Optional[str] = None,
    ):
        config = PROVIDER_CONFIG[provider]
        self.model = model or config["default_model"]
        self.client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])

    def chat(self, messages: list[dict], temperature: float = 0.3) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
