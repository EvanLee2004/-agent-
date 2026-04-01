"""原生 function calling 运行时。"""

import re
from typing import Any

from infrastructure.llm import LLMClient
from tools.registry import ToolRegistry
from tools.schemas import ToolExecutionResult, ToolRuntimeResult


class ToolRuntime:
    """工具运行时。

    主循环规则：
    1. 第一轮强制模型调用至少一个工具
    2. 工具执行结果写回消息历史
    3. 后续轮次允许模型继续调工具或直接生成最终答复

    这样既能保证“不是自由聊天”，也能让模型在拿到工具结果后自然收束。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        max_steps: int = 8,
    ):
        self._llm_client = llm_client
        self._tool_registry = tool_registry
        self._max_steps = max_steps

    def run(
        self,
        user_input: str,
        system_prompt: str,
    ) -> ToolRuntimeResult:
        """执行完整工具链路。"""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        executed_tool_names: list[str] = []
        tool_results: list[ToolExecutionResult] = []

        for step in range(self._max_steps):
            tool_choice = "required" if step == 0 else "auto"
            response = self._llm_client.chat_with_tools(
                messages=messages,
                tools=self._tool_registry.get_openai_tools(),
                tool_choice=tool_choice,
            )
            if not response.success:
                raise RuntimeError(response.error_message or "工具调用失败")

            if response.assistant_message:
                messages.append(response.assistant_message)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    result = self._tool_registry.execute(
                        tool_name=tool_call.name,
                        arguments=tool_call.arguments,
                    )
                    executed_tool_names.append(tool_call.name)
                    tool_results.append(result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result.to_tool_message_content(),
                        }
                    )
                continue

            if not executed_tool_names:
                raise RuntimeError("模型未调用任何工具，主流程拒绝退回自由聊天")

            final_reply = self._sanitize_final_reply(response.content)
            if not final_reply:
                raise RuntimeError("模型未生成最终回复")

            return ToolRuntimeResult(
                final_reply=final_reply,
                executed_tool_names=executed_tool_names,
                tool_results=tool_results,
            )

        raise RuntimeError("工具调用轮次超限，请检查 prompt 或工具设计")

    @staticmethod
    def _sanitize_final_reply(content: str) -> str:
        """清理最终面向用户的答复文本。

        某些 OpenAI-compatible provider 会在 `content` 中混入 `<think>...</think>`
        推理内容。工具调用主流程已经不再依赖这些文本做协议解析，因此这里可以在
        最终返回用户前安全移除，避免把推理过程直接暴露出来。
        """
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()
