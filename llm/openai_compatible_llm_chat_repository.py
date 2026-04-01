"""OpenAI-compatible LLM 仓储实现。"""

import json
import time
from typing import Any
from typing import Optional

from openai import APIConnectionError, APITimeoutError, OpenAI, OpenAIError, RateLimitError

from configuration.llm_configuration import LlmConfiguration
from llm.llm_chat_repository import LlmChatRepository
from llm.llm_chat_request import LlmChatRequest
from llm.llm_error import LlmError
from llm.llm_message import LlmMessage
from llm.llm_response import LlmResponse
from llm.llm_tool_call import LlmToolCall


MAX_RETRY_COUNT = 3
TIMEOUT_RETRY_DELAY_SECONDS = 1
RATE_LIMIT_RETRY_DELAY_SECONDS = 2


class OpenAiCompatibleLlmChatRepository(LlmChatRepository):
    """OpenAI-compatible LLM 仓储实现。"""

    def __init__(self, configuration: LlmConfiguration):
        self._configuration = configuration
        self._client = OpenAI(
            api_key=configuration.api_key,
            base_url=configuration.base_url,
        )

    def send_chat_request(self, chat_request: LlmChatRequest) -> LlmResponse:
        """发送聊天请求并统一处理重试。

        Args:
            chat_request: 归一化后的聊天请求。

        Returns:
            统一后的响应对象。
        """
        last_error: Optional[Exception] = None
        for retry_index in range(MAX_RETRY_COUNT):
            try:
                response = self._send_single_request(chat_request)
                return self._normalize_response(response)
            except (APITimeoutError, APIConnectionError, RateLimitError) as error:
                last_error = error
                if self._should_stop_retrying(retry_index):
                    break
                self._sleep_before_retry(error, retry_index)
            except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
                return self._build_failure_response(f"LLM 响应处理失败: {str(error)}")
            except (OpenAIError, LlmError) as error:
                return self._build_failure_response(f"LLM 调用失败: {str(error)}")

        return self._build_retry_exhausted_response(last_error)

    def _send_single_request(self, chat_request: LlmChatRequest) -> Any:
        """发送单次 provider 请求。"""
        return self._client.chat.completions.create(
            model=self._configuration.model_name,
            messages=[message.to_dict() for message in chat_request.messages],  # type: ignore[arg-type]
            tools=chat_request.tools,
            tool_choice=chat_request.tool_choice,
            temperature=chat_request.temperature,
            timeout=chat_request.timeout,
        )

    def _should_stop_retrying(self, retry_index: int) -> bool:
        """判断当前轮是否已经没有重试空间。"""
        return retry_index >= MAX_RETRY_COUNT - 1

    def _sleep_before_retry(self, error: Exception, retry_index: int) -> None:
        """按错误类型执行退避等待。"""
        if isinstance(error, APITimeoutError):
            time.sleep(TIMEOUT_RETRY_DELAY_SECONDS + retry_index)
            return
        if isinstance(error, APIConnectionError):
            time.sleep(2**retry_index)
            return
        time.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)

    def _build_failure_response(self, error_message: str) -> LlmResponse:
        """构造失败响应。"""
        return LlmResponse(
            content="",
            usage={},
            model_name=self._configuration.model_name,
            success=False,
            error_message=error_message,
        )

    def _build_retry_exhausted_response(self, last_error: Optional[Exception]) -> LlmResponse:
        """构造重试耗尽后的失败响应。"""
        return self._build_failure_response(
            f"LLM 调用失败，已重试 {MAX_RETRY_COUNT} 次: {str(last_error)}"
        )

    def _normalize_response(self, response: Any) -> LlmResponse:
        """把 provider 响应转换为统一模型。

        Args:
            response: OpenAI-compatible SDK 响应对象。

        Returns:
            统一后的响应对象。

        Raises:
            IndexError: provider 未返回 choices。
            AttributeError: provider 响应对象缺少必要字段。
            json.JSONDecodeError: 工具参数不是合法 JSON。
            TypeError: 工具参数不是 JSON 对象。
        """
        choice = response.choices[0]
        message = choice.message
        usage = self._normalize_usage(response)
        content = message.content or ""
        tool_calls = self._normalize_tool_calls(message.tool_calls or [])
        assistant_message = self._build_assistant_message(content, tool_calls)
        return LlmResponse(
            content=content,
            usage=usage,
            model_name=self._configuration.model_name,
            success=True,
            tool_calls=tool_calls,
            finish_reason=getattr(choice, "finish_reason", None),
            assistant_message=assistant_message,
        )

    def _normalize_usage(self, response: Any) -> dict:
        """提取 usage 信息。

        Args:
            response: provider 响应对象。

        Returns:
            标准化后的 token 统计。
        """
        if not hasattr(response, "usage") or not response.usage:
            return {}

        return {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    def _normalize_tool_calls(self, raw_tool_calls: list[Any]) -> list[LlmToolCall]:
        """标准化工具调用列表。

        Args:
            raw_tool_calls: provider 返回的原始工具调用列表。

        Returns:
            归一化后的工具调用列表。
        """
        return [self._normalize_single_tool_call(raw_tool_call) for raw_tool_call in raw_tool_calls]

    def _normalize_single_tool_call(self, raw_tool_call: Any) -> LlmToolCall:
        """标准化单个工具调用。"""
        function_call = raw_tool_call.function
        raw_arguments = function_call.arguments or "{}"
        arguments = json.loads(raw_arguments)
        if not isinstance(arguments, dict):
            raise TypeError(f"工具 {function_call.name} 参数必须是 JSON 对象")
        return LlmToolCall(
            call_id=str(raw_tool_call.id),
            tool_name=str(function_call.name),
            arguments=arguments,
            raw_arguments=raw_arguments,
        )

    def _build_assistant_message(
        self,
        content: str,
        tool_calls: list[LlmToolCall],
    ) -> LlmMessage:
        """构造标准化 assistant 消息。

        Args:
            content: 文本内容。
            tool_calls: 归一化后的工具调用列表。

        Returns:
            标准化消息对象。
        """
        return LlmMessage(
            role="assistant",
            content=content,
            tool_calls=[self._build_tool_call_message(tool_call) for tool_call in tool_calls],
        )

    def _build_tool_call_message(self, tool_call: LlmToolCall) -> dict[str, Any]:
        """构造 assistant 消息中的单个工具调用。"""
        return {
            "id": tool_call.call_id,
            "type": "function",
            "function": {
                "name": tool_call.tool_name,
                "arguments": tool_call.raw_arguments,
            },
        }
