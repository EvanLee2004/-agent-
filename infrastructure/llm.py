"""LLM 客户端与 provider 适配层。

当前项目已经从“让模型输出 JSON，再由本地解析执行”的模式，
升级到“让模型通过原生 function calling 触发工具”的模式。

因此这一层需要同时解决两件事：
1. 隔离 OpenAI SDK/OpenAI-compatible SDK 的细节
2. 为上层提供稳定的 `chat_with_tools()` 接口

设计原则：
- Agent 和 ToolRuntime 不直接依赖第三方 SDK 响应对象
- provider 能力判断集中在这一层，不散落到业务层
- 普通聊天与工具调用都复用同一套重试、超时和错误处理策略
"""

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError

from providers import get_provider


load_dotenv()
CONFIG_FILE = Path("config.json")


class LLMError(Exception):
    """LLM 调用异常。"""

    pass


@dataclass
class LLMToolCall:
    """模型返回的一次工具调用。

    Attributes:
        id: provider 返回的工具调用标识。
        name: 工具名称。
        arguments: 已解析为字典的工具参数。
        raw_arguments: provider 返回的原始 JSON 字符串，便于排查线上问题。
    """

    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str


@dataclass
class LLMResponse:
    """统一后的 LLM 响应对象。"""

    content: str
    usage: dict
    model: str
    success: bool = True
    error_message: Optional[str] = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    assistant_message: Optional[dict[str, Any]] = None


class LLMProvider(ABC):
    """LLM provider 抽象接口。"""

    @property
    @abstractmethod
    def supports_native_tool_calling(self) -> bool:
        """当前 provider 是否支持原生 function calling。"""
        pass

    @abstractmethod
    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> LLMResponse:
        """带原生工具定义的聊天调用。"""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible provider 实现。

    当前 MiniMax、DeepSeek 与 OpenAI 都通过这一实现适配，
    因为它们对外暴露的是兼容 `chat.completions.create()` 的接口。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        supports_native_tool_calling: bool = True,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._supports_native_tool_calling = supports_native_tool_calling
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    @property
    def supports_native_tool_calling(self) -> bool:
        """当前 provider 是否支持原生 function calling。"""
        return self._supports_native_tool_calling

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.3,
        timeout: int = 30,
    ) -> LLMResponse:
        """发送原生 function calling 请求。"""
        if not self.supports_native_tool_calling:
            return LLMResponse(
                content="",
                usage={},
                model=self._model,
                success=False,
                error_message="当前 provider 未启用原生 function calling 支持",
            )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            timeout=timeout,
        )
        return self._normalize_response(response)

    def _normalize_response(self, response: Any) -> LLMResponse:
        """把 SDK 响应转换为项目内部统一对象。"""
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        try:
            choice = response.choices[0]
            message = choice.message
        except (IndexError, AttributeError):
            return LLMResponse(
                content="",
                usage=usage,
                model=self._model,
                success=False,
                error_message="LLM 响应格式异常",
            )

        content = message.content or ""
        tool_calls: list[LLMToolCall] = []
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": content,
        }

        raw_tool_calls = getattr(message, "tool_calls", None) or []
        if raw_tool_calls:
            assistant_message["tool_calls"] = []
            for tool_call in raw_tool_calls:
                function_call = getattr(tool_call, "function", None)
                if function_call is None:
                    return LLMResponse(
                        content=content,
                        usage=usage,
                        model=self._model,
                        success=False,
                        error_message="工具调用缺少 function 字段",
                    )

                raw_arguments = function_call.arguments or "{}"
                try:
                    parsed_arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    return LLMResponse(
                        content=content,
                        usage=usage,
                        model=self._model,
                        success=False,
                        error_message=(
                            f"工具 {function_call.name} 返回了无法解析的参数: {raw_arguments}"
                        ),
                    )

                if not isinstance(parsed_arguments, dict):
                    return LLMResponse(
                        content=content,
                        usage=usage,
                        model=self._model,
                        success=False,
                        error_message=f"工具 {function_call.name} 参数必须是 JSON 对象",
                    )

                normalized_call = LLMToolCall(
                    id=str(tool_call.id),
                    name=str(function_call.name),
                    arguments=parsed_arguments,
                    raw_arguments=raw_arguments,
                )
                tool_calls.append(normalized_call)
                assistant_message["tool_calls"].append(
                    {
                        "id": normalized_call.id,
                        "type": "function",
                        "function": {
                            "name": normalized_call.name,
                            "arguments": normalized_call.raw_arguments,
                        },
                    }
                )

        return LLMResponse(
            content=content,
            usage=usage,
            model=self._model,
            success=True,
            tool_calls=tool_calls,
            finish_reason=getattr(choice, "finish_reason", None),
            assistant_message=assistant_message,
        )


class LLMClient:
    """LLM 客户端 façade，单例模式。"""

    _instance: Optional["LLMClient"] = None

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider_name: str = "openai_compatible",
        supports_native_tool_calling: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.provider_name = provider_name
        self.provider: LLMProvider = OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
            supports_native_tool_calling=supports_native_tool_calling,
        )

    @classmethod
    def get_instance(cls) -> "LLMClient":
        """获取单例实例。"""
        if cls._instance is None:
            config = cls._load_config()
            if not config:
                raise RuntimeError("未配置 LLM，请先运行配置")

            api_key = os.getenv("LLM_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError("未设置 LLM_API_KEY，请在 .env 中配置")

            provider_name = str(config.get("provider", "")).strip()
            provider_config = get_provider(provider_name)
            supports_native_tool_calling = True
            if provider_config is not None:
                supports_native_tool_calling = provider_config.supports_native_tool_calling

            cls._instance = cls(
                api_key=api_key,
                base_url=config.get("base_url", "https://api.minimax.chat/v1"),
                model=config["model"],
                provider_name=provider_name or "openai_compatible",
                supports_native_tool_calling=supports_native_tool_calling,
            )
        return cls._instance

    @classmethod
    def _load_config(cls) -> Optional[dict]:
        """从 config.json 加载配置。"""
        if not CONFIG_FILE.exists():
            CONFIG_FILE.parent.mkdir(exist_ok=True)
            return None

        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return None

    @classmethod
    def reset_instance(cls) -> None:
        """重置实例（配置变更后调用）。"""
        cls._instance = None

    @property
    def supports_native_tool_calling(self) -> bool:
        """当前 provider 是否支持原生 function calling。"""
        return self.provider.supports_native_tool_calling

    def require_native_tool_calling(self) -> None:
        """要求当前 provider 支持原生 function calling。"""
        if not self.supports_native_tool_calling:
            raise LLMError(
                f"当前 provider {self.provider_name} 不支持原生 function calling"
            )

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.3,
        max_retries: int = 3,
        timeout: int = 30,
    ) -> LLMResponse:
        """发送原生 function calling 请求。"""
        self.require_native_tool_calling()
        return self._run_with_retry(
            callable_name="chat_with_tools",
            temperature=temperature,
            max_retries=max_retries,
            timeout=timeout,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )

    def _run_with_retry(
        self,
        callable_name: str,
        temperature: float,
        max_retries: int,
        timeout: int,
        **kwargs: Any,
    ) -> LLMResponse:
        """统一的 provider 调用重试逻辑。

        Args:
            callable_name: provider 上的方法名。
            temperature: 温度参数。
            max_retries: 最大重试次数。
            timeout: 超时时间。
            **kwargs: 透传给 provider 的额外参数。

        Returns:
            LLMResponse: 统一后的响应对象。
        """
        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                provider_callable = getattr(self.provider, callable_name)
                return provider_callable(
                    temperature=temperature,
                    timeout=timeout,
                    **kwargs,
                )
            except APITimeoutError as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    time.sleep(attempt + 1)
            except APIConnectionError as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
            except RateLimitError as exc:
                last_error = exc
                if attempt < max_retries - 1:
                    time.sleep(2)
            except Exception as exc:
                return LLMResponse(
                    content="",
                    usage={},
                    model=self.model,
                    success=False,
                    error_message=f"服务暂时不可用: {str(exc)}",
                )

        return LLMResponse(
            content="",
            usage={},
            model=self.model,
            success=False,
            error_message=f"LLM 调用失败，已重试 {max_retries} 次: {str(last_error)}",
        )
