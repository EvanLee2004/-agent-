"""会话回复净化器。"""

import re


THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


class ReplyTextSanitizer:
    """清理底层运行时泄漏到最终回复中的内部思考内容。

    某些模型或上游 runtime 在最终文本前会附带 `<think>...</think>` 片段。
    这些内容对最终用户既没有价值，也会破坏产品观感，因此应在会话边界统一清理，
    而不是把清洗逻辑散落到 CLI、测试或业务服务里。
    """

    def sanitize(self, reply_text: str) -> str:
        """净化最终回复文本。

        Args:
            reply_text: 底层运行时返回的原始文本。

        Returns:
            清理内部思考片段后的用户可见文本。
        """
        sanitized_text = THINK_BLOCK_PATTERN.sub("", reply_text).strip()
        if sanitized_text:
            return sanitized_text
        return reply_text.strip()
