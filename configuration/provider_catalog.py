"""Provider 目录服务。"""

from typing import Optional

from configuration.provider_metadata import ProviderMetadata


class ProviderCatalog:
    """提供商目录。

    目录被收敛成一个独立类，是为了让配置服务和 LLM 网关使用同一份事实来源，
    避免能力判断散落在多个模块里。
    """

    PROVIDERS: dict[str, ProviderMetadata] = {
        "minimax": ProviderMetadata(
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
            base_url="https://api.minimax.chat/v1",
            supports_tool_calling=True,
            allow_custom_models=True,
        ),
        "deepseek": ProviderMetadata(
            name="DeepSeek",
            models=["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
            default_model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            supports_tool_calling=True,
            allow_custom_models=True,
        ),
        "openai": ProviderMetadata(
            name="OpenAI",
            models=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
            default_model="gpt-4.1-mini",
            base_url="https://api.openai.com/v1",
            supports_tool_calling=True,
            allow_custom_models=True,
        ),
    }

    def get_provider(self, provider_name: str) -> Optional[ProviderMetadata]:
        """按名称获取 provider。

        Args:
            provider_name: provider 唯一标识。

        Returns:
            对应的 provider 元数据；不存在时返回 `None`。
        """
        return self.PROVIDERS.get(provider_name)

    def list_provider_names(self) -> list[str]:
        """列出全部 provider 名称。

        Returns:
            支持的 provider 名称列表。
        """
        return list(self.PROVIDERS.keys())
