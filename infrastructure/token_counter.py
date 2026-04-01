"""Token 计数器模块。

提供 token 计数功能：
1. 从文本估算（基于字符的近似计算）
2. 从 API 响应提取 usage

无需依赖外部库即可追踪 token 使用情况。
"""

from typing import Optional


class TokenCounter:
    """Token 计数器，支持估算和 API 响应提取两种方式。"""

    @staticmethod
    def estimate_from_text(text: str) -> int:
        """使用基于字符的近似计算估算文本的 token 数量。

        近似规则（参考 OpenAI 的 tokenizer）：
        - 中文字符：每个约 1.5 个 token（因模型而异）
        - 英文字符：每 4 个字符约 1 个 token
        这是 API 调用前的粗略估算

        Args:
            text: 输入文本字符串。

        Returns:
            估算的 token 数量。
        """
        if not text:
            return 0

        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars

        return int(chinese_chars * 1.5 + other_chars / 4)

    @staticmethod
    def estimate_messages(messages: list[dict]) -> int:
        """估算消息列表的总 token 数量。

        每条消息的角色标记约有 4 个 token 的开销。

        Args:
            messages: 消息字典列表，包含 'role' 和 'content' 键。

        Returns:
            估算的总 token 数量。
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += TokenCounter.estimate_from_text(content)
            total += 4
        return total

    @staticmethod
    def from_api_response(usage: Optional[dict]) -> int:
        """从 API 响应 usage 中提取总 token 数量。

        Args:
            usage: API 响应 usage 字典，包含：
                - total_tokens: 总计（如果可用）
                - prompt_tokens + completion_tokens: 备用

        Returns:
            API 返回的总 token 数量。
        """
        if not usage:
            return 0

        if "total_tokens" in usage:
            return usage["total_tokens"]

        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        return prompt + completion

    @staticmethod
    def get_prompt_tokens(usage: Optional[dict]) -> int:
        """从 API 响应提取输入 token 数量。

        Args:
            usage: API 响应 usage 字典。

        Returns:
            输入 token 数量。
        """
        if not usage:
            return 0
        return usage.get("prompt_tokens", 0)

    @staticmethod
    def get_completion_tokens(usage: Optional[dict]) -> int:
        """从 API 响应提取输出 token 数量。

        Args:
            usage: API 响应 usage 字典。

        Returns:
            输出 token 数量。
        """
        if not usage:
            return 0
        return usage.get("completion_tokens", 0)
