"""模型提供商定义"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderConfig:
    """提供商配置"""
    name: str                    # 显示名称
    models: list[str]           # 可用模型列表
    default_model: str          # 默认模型
    base_url_template: str     # API URL 模板


# Provider 定义（可扩展）
PROVIDERS: dict[str, ProviderConfig] = {
    "minimax": ProviderConfig(
        name="MiniMax",
        models=["MiniMax-M2.7"],
        default_model="MiniMax-M2.7",
        base_url_template="https://api.minimax.chat/v1",
    ),
    "deepseek": ProviderConfig(
        name="DeepSeek",
        models=["deepseek-chat", "deepseek-coder"],
        default_model="deepseek-chat",
        base_url_template="https://api.deepseek.com/v1",
    ),
}


def get_provider(name: str) -> ProviderConfig | None:
    """获取 provider 配置"""
    return PROVIDERS.get(name)


def list_providers() -> list[str]:
    """列出所有 provider"""
    return list(PROVIDERS.keys())
