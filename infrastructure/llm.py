"""LLM 客户端模块"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError


load_dotenv()
CONFIG_FILE = Path("config.json")


class LLMError(Exception):
    """LLM 调用异常"""

    pass


@dataclass
class LLMResponse:
    """LLM 响应"""

    content: str
    usage: dict
    model: str
    success: bool = True
    error_message: Optional[str] = None


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
        """获取单例实例"""
        if cls._instance is None:
            config = cls._load_config()
            if not config:
                raise RuntimeError("未配置 LLM，请先运行配置")
            api_key = os.getenv("LLM_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError("未设置 LLM_API_KEY，请在 .env 中配置")
            cls._instance = cls(
                api_key=api_key,
                base_url=config.get("base_url", "https://api.minimax.chat/v1"),
                model=config["model"],
            )
        return cls._instance

    @classmethod
    def _load_config(cls) -> Optional[dict]:
        """从 config.json 加载配置"""
        if not CONFIG_FILE.exists():
            CONFIG_FILE.parent.mkdir(exist_ok=True)
            return None
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return None

    @classmethod
    def reset_instance(cls) -> None:
        """重置实例（配置变更后调用）"""
        cls._instance = None

    def chat(
        self,
        messages: list[Any],
        temperature: float = 0.3,
        max_retries: int = 3,
        timeout: int = 30,
    ) -> LLMResponse:
        """发送聊天请求，带重试和超时控制

        Args:
            messages: 对话消息列表
            temperature: 温度参数
            max_retries: 最大重试次数
            timeout: 超时秒数

        Returns:
            LLMResponse 对象
        """
        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore
                    temperature=temperature,
                    timeout=timeout,
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
                    return LLMResponse(
                        content="",
                        usage={},
                        model=self.model,
                        success=False,
                        error_message="LLM 响应格式异常",
                    )

                return LLMResponse(content=content, usage=usage, model=self.model)

            except APITimeoutError as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))

            except APIConnectionError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    time.sleep(wait_time)

            except RateLimitError as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(2)

            except Exception as e:
                return LLMResponse(
                    content="",
                    usage={},
                    model=self.model,
                    success=False,
                    error_message=f"服务暂时不可用: {str(e)}",
                )

        return LLMResponse(
            content="",
            usage={},
            model=self.model,
            success=False,
            error_message=f"LLM 调用失败，已重试 {max_retries} 次: {str(last_error)}",
        )
