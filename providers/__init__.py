"""模型提供商定义。

这里把“提供商元数据”集中收口，避免这些能力判断散落在 Agent、LLM Client
和配置验证器里。当前项目接入原生 function calling 后，提供商配置除了基础
URL 和模型列表之外，还需要显式描述两个能力：

1. 是否支持原生 tool/function calling
2. 是否允许用户填写自定义模型名

这样可以让配置层和运行时都基于同一份事实做判断。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderConfig:
    """提供商配置。

    Attributes:
        name: 提供商展示名称。
        models: 推荐模型列表，用于交互式配置时展示。
        default_model: 默认模型名称。
        base_url_template: API 基础地址模板。
        supports_native_tool_calling: 是否支持原生 function calling。
        allow_custom_models: 是否允许使用不在推荐列表中的自定义模型。
    """

    name: str
    models: list[str]
    default_model: str
    base_url_template: str
    supports_native_tool_calling: bool = False
    allow_custom_models: bool = False


# Provider 定义（可扩展）。
# 这里保留当前项目已有 provider，并补充 OpenAI 作为原生 tool calling 的
# 标准对照 provider。MiniMax 与 DeepSeek 的能力定义参考其官方 OpenAI
# 兼容文档；模型列表则偏向“推荐值”，不强制穷尽。
PROVIDERS: dict[str, ProviderConfig] = {
    "minimax": ProviderConfig(
        name="MiniMax",
        models=[
            "MiniMax-M2.7",
            "MiniMax-M2.5",
            "MiniMax-M2.5-highspeed",
            "MiniMax-M2.1",
            "MiniMax-M2.1-highspeed",
            "MiniMax-M2",
        ],
        default_model="MiniMax-M2.7",
        base_url_template="https://api.minimax.chat/v1",
        supports_native_tool_calling=True,
        allow_custom_models=True,
    ),
    "deepseek": ProviderConfig(
        name="DeepSeek",
        models=["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
        default_model="deepseek-chat",
        base_url_template="https://api.deepseek.com/v1",
        supports_native_tool_calling=True,
        allow_custom_models=True,
    ),
    "openai": ProviderConfig(
        name="OpenAI",
        models=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
        default_model="gpt-4.1-mini",
        base_url_template="https://api.openai.com/v1",
        supports_native_tool_calling=True,
        allow_custom_models=True,
    ),
}


def get_provider(name: str) -> Optional[ProviderConfig]:
    """获取 provider 配置。"""
    return PROVIDERS.get(name)


def list_providers() -> list[str]:
    """列出所有 provider。"""
    return list(PROVIDERS.keys())
