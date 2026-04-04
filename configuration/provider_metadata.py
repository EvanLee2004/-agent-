"""Provider 元数据模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderMetadata:
    """模型提供商元数据。

    Attributes:
        models: 推荐模型列表。
        supports_tool_calling: 是否支持工具调用能力。
        allow_custom_models: 是否允许使用自定义模型名。
    """

    models: list[str]
    supports_tool_calling: bool
    allow_custom_models: bool
