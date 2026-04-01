"""上下文压缩模块。

当 token 数量接近限制时处理上下文窗口压缩。
参考 OpenCode 的做法：
- 在 context window 的 95% 时触发压缩
- 使用 LLM 生成对话摘要
- 用摘要消息替换历史记录

这使得长对话可以持续进行而不会触及上下文限制。
"""

from typing import Optional

from core.llm import LLMClient
from core.models import get_default_model, get_context_window


COMPACTION_THRESHOLD = 0.95

SUMMARIZE_SYSTEM_PROMPT = """你是一个乐于助人的助手，负责总结对话。

你的任务是对上面的对话进行详细但简洁的总结。
重点关注对继续对话有帮助的信息，包括：
- 我们完成了什么或讨论了什么
- 当前状态或进展
- 做出的重要决定
- 待完成的任务或下一步
- 任何重要的上下文，如文件名、数字或具体细节

保留具体的细节，如姓名、数字、日期和文件路径，因为它们可能很重要。"""


SUMMARIZE_USER_PROMPT = """请简洁地总结这段对话：

{history}

摘要："""


class Compactor:
    """上下文压缩器，使用摘要保持在上下文限制内。

    Attributes:
        model: LLM 调用的模型名称。
        context_window: 以 token 为单位的上下文窗口大小。
        threshold: 压缩触发阈值（默认 95%）。
        threshold_tokens: 触发压缩的绝对 token 数量。
    """

    def __init__(
        self,
        model: Optional[str] = None,
        threshold: float = COMPACTION_THRESHOLD,
    ):
        """初始化压缩器。

        Args:
            model: 模型名称。如果为 None，使用配置中的默认值。
            threshold: 压缩触发阈值（0.0 到 1.0）。
        """
        self.model = model or get_default_model()
        self.context_window = get_context_window(self.model)
        self.threshold = threshold
        self.threshold_tokens = int(self.context_window * threshold)

    def should_compact(self, token_count: int) -> bool:
        """检查 token 数量是否超过压缩阈值。

        Args:
            token_count: 当前估算的 token 数量。

        Returns:
            如果 token_count >= threshold_tokens 返回 True，否则返回 False。
        """
        return token_count >= self.threshold_tokens

    def summarize(self, messages: list[dict]) -> str:
        """使用 LLM 生成对话摘要。

        Args:
            messages: 包含 'role' 和 'content' 的对话消息列表。

        Returns:
            LLM 生成的摘要字符串。
        """
        history_text = self._format_history(messages)

        summarize_messages = [
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": SUMMARIZE_USER_PROMPT.format(history=history_text),
            },
        ]

        try:
            response = LLMClient.get_instance().chat(
                messages=summarize_messages,
                temperature=0.3,
            )
            return response.content.strip()
        except Exception as e:
            return f"[Summary failed: {str(e)}]"

    def compact(self, messages: list[dict]) -> tuple[list[dict], str]:
        """将对话历史压缩成摘要。

        使用 LLM 生成摘要，并返回用单个摘要消息替换原始消息的新消息列表。

        Args:
            messages: 原始对话消息。

        Returns:
            元组 (new_messages, summary)，其中：
                - new_messages: 用摘要替换历史后的消息
                - summary: 生成的摘要文本
        """
        summary = self.summarize(messages)

        summary_message = {
            "role": "assistant",
            "content": f"[Previous conversation summary]\n{summary}",
        }

        return [summary_message], summary

    @staticmethod
    def _format_history(messages: list[dict]) -> str:
        """将消息格式化为可读的对话历史字符串。

        Args:
            messages: 包含 'role' 和 'content' 的消息字典列表。

        Returns:
            每条消息一行的格式化字符串。
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)
