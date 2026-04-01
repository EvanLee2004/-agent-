"""工具使用策略。"""


class ToolUsePolicy:
    """工具使用策略。

    该策略不替模型做硬路由，只负责识别少量需要更高事实约束的场景，
    例如记忆召回必须先查询记忆源。
    """

    MEMORY_RECALL_PATTERNS = (
        "你还记得",
        "还记得我",
        "我之前说过什么",
        "我之前让你记住",
        "之前让你记住",
        "你记住了什么",
        "记住了什么",
        "记得什么",
        "我的偏好是什么",
        "我有什么偏好",
        "你知道我的偏好",
        "你都记了什么",
        "你都记住了什么",
        "之前记了什么",
        "之前记住了什么",
    )

    def is_memory_recall_request(self, user_input: str) -> bool:
        """判断是否属于记忆召回请求。

        Args:
            user_input: 用户原始输入。

        Returns:
            是否属于记忆召回场景。
        """
        normalized_input = "".join(user_input.strip().lower().split())
        return any(pattern in normalized_input for pattern in self.MEMORY_RECALL_PATTERNS)
