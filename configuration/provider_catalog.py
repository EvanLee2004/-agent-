"""Provider 目录服务。"""

from configuration.provider_metadata import ProviderMetadata


class ProviderCatalog:
    """提供商目录。

    目录被收敛成一个独立类，是为了让配置服务和 LLM 网关使用同一份事实来源，
    避免能力判断散落在多个模块里。
    """

    PROVIDERS: dict[str, ProviderMetadata] = {
        "minimax": ProviderMetadata(
            models=[
                "MiniMax-M2.7",
                "MiniMax-M2.5",
                "MiniMax-M2.5-highspeed",
                "MiniMax-M2.1",
                "MiniMax-M2.1-highspeed",
                "MiniMax-M2",
            ],
            supports_tool_calling=True,
            allow_custom_models=True,
        ),
        "deepseek": ProviderMetadata(
            models=["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
            supports_tool_calling=True,
            allow_custom_models=True,
        ),
        "openai": ProviderMetadata(
            models=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
            supports_tool_calling=True,
            allow_custom_models=True,
        ),
    }

    def get_provider(self, provider_name: str) -> ProviderMetadata | None:
        """按名称获取 provider。

        Args:
            provider_name: provider 唯一标识。

        Returns:
            对应的 provider 元数据；不存在时返回 `None`。
        """
        return self.PROVIDERS.get(provider_name)
