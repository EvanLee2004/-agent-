"""LLM 使用量模型。

描述 DeerFlow 一次完整 turn 的 LLM API 调用计量信息。
这些数据属于内部遥测，不暴露给用户，但在审计和产品分析中有价值。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LlmUsage:
    """LLM token 使用量。

    Attributes:
        input_tokens: 输入 token 数量。
        output_tokens: 输出 token 数量。
        total_tokens: 总 token 数量。
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int
