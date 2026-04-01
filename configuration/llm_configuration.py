"""LLM 配置模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LlmConfiguration:
    """LLM 运行配置。

    Attributes:
        provider_name: 提供商标识。
        model_name: 模型名称。
        base_url: API 基础地址。
        api_key: API 密钥。
    """

    provider_name: str
    model_name: str
    base_url: str
    api_key: str
