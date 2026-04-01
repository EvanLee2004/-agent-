"""工具循环请求模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolLoopRequest:
    """工具循环请求。

    Attributes:
        user_input: 用户输入。
        system_prompt: 聚合后的系统提示词。
    """

    user_input: str
    system_prompt: str
