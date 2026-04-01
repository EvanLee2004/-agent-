"""LLM 客户端模块"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from openai import OpenAI


CONFIG_FILE = Path("config.json")


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    usage: dict
    model: str


class LLMClient:
    """LLM 客户端，单例模式"""
    _instance: Optional["LLMClient"] = None

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    @classmethod
    def get_instance(cls) -> "LLMClient":
        """获取单例实例，配置从 config.json 读取"""
        if cls._instance is None:
            config = cls._load_config()
            if not config:
                raise RuntimeError("未配置 LLM，请先运行配置")
            cls._instance = cls(
                api_key=config["api_key"],
                base_url=config.get("base_url", "https://api.minimax.chat/v1"),
                model=config["model"],
            )
        return cls._instance

    @classmethod
    def _load_config(cls) -> Optional[dict]:
        """从 config.json 加载配置"""
        if not CONFIG_FILE.exists():
            return None
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return None

    @classmethod
    def reset_instance(cls) -> None:
        """重置实例（配置变更后调用）"""
        cls._instance = None

    def chat(self, messages: list[dict], temperature: float = 0.3) -> LLMResponse:
        """发送聊天请求"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        content = ""
        try:
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content or ""
        except (IndexError, AttributeError):
            raise RuntimeError(f"LLM 响应格式异常: {response}")

        return LLMResponse(content=content, usage=usage, model=self.model)
