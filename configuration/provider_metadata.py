"""Provider 元数据模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderMetadata:
    """模型提供商元数据。

    Attributes:
        name: 提供商展示名称。
        models: 推荐模型列表。
        default_model: 默认模型。
        base_url: API 基础地址。
        default_api_key_env: 推荐使用的 API Key 环境变量名。
        supports_tool_calling: 是否支持工具调用能力。
        allow_custom_models: 是否允许使用自定义模型名。
    """

    name: str
    models: list[str]
    default_model: str
    base_url: str
    default_api_key_env: str
    supports_tool_calling: bool
    allow_custom_models: bool
