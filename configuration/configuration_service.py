"""配置服务。"""

from configuration.configuration_error import ConfigurationError
from configuration.configuration_repository import ConfigurationRepository
from configuration.llm_configuration import LlmConfiguration
from configuration.provider_catalog import ProviderCatalog


class ConfigurationService:
    """配置服务。

    该服务负责把交互式配置、配置校验和配置恢复收敛到同一层，
    避免 CLI、LLM 网关和启动流程各自维护一套校验逻辑。
    """

    REQUIRED_KEYS = ("provider", "model", "base_url")

    def __init__(
        self,
        configuration_repository: ConfigurationRepository,
        provider_catalog: ProviderCatalog,
    ):
        self._configuration_repository = configuration_repository
        self._provider_catalog = provider_catalog

    def ensure_configuration(self) -> LlmConfiguration:
        """确保系统存在可用配置。

        Returns:
            已校验的 LLM 配置。

        Raises:
            ConfigurationError: 配置缺失、无效或缺少 API 密钥时抛出。
        """
        normalized_config = self._load_normalized_config()
        api_key = self._load_api_key()
        return LlmConfiguration(
            provider_name=normalized_config["provider"],
            model_name=normalized_config["model"],
            base_url=normalized_config["base_url"],
            api_key=api_key,
        )

    def _load_normalized_config(self) -> dict:
        """读取并校验配置文件。"""
        config_data = self._configuration_repository.load_config_data()
        if not config_data:
            raise ConfigurationError("缺少 config.json，请先完成模型配置")
        return self._validate_config_data(config_data)

    def _load_api_key(self) -> str:
        """读取并校验 API Key。"""
        api_key = self._configuration_repository.load_api_key()
        if not api_key:
            raise ConfigurationError("缺少 LLM_API_KEY，请在 .env 中配置")
        return api_key

    def save_configuration(self, configuration: LlmConfiguration) -> None:
        """保存配置。

        Args:
            configuration: 已经确认过的运行配置。
        """
        self._configuration_repository.save_config_data(
            {
                "provider": configuration.provider_name,
                "model": configuration.model_name,
                "base_url": configuration.base_url,
            }
        )
        self._configuration_repository.save_api_key(configuration.api_key)

    def _validate_config_data(self, config_data: dict) -> dict:
        """校验并规范化配置字典。

        Args:
            config_data: 原始配置字典。

        Returns:
            通过校验的配置字典。

        Raises:
            ConfigurationError: 配置不合法时抛出。
        """
        self._require_dict(config_data)
        self._require_keys(config_data)
        provider_name, provider = self._resolve_provider(config_data)
        model_name = self._resolve_model_name(config_data, provider_name, provider)
        return {
            "provider": provider_name,
            "model": model_name,
            "base_url": str(config_data["base_url"]).strip(),
        }

    def _require_dict(self, config_data: dict) -> None:
        """校验配置必须是字典对象。"""
        if not isinstance(config_data, dict):
            raise ConfigurationError("配置格式错误：config.json 必须是对象")

    def _require_keys(self, config_data: dict) -> None:
        """校验配置中的必填字段。"""
        for key in self.REQUIRED_KEYS:
            if not config_data.get(key):
                raise ConfigurationError(f"配置缺少必填字段: {key}")

    def _resolve_provider(self, config_data: dict):
        """解析并校验 provider。"""
        provider_name = str(config_data["provider"]).strip()
        provider = self._provider_catalog.get_provider(provider_name)
        if provider is None:
            raise ConfigurationError(f"不支持的 provider: {provider_name}")
        if not provider.supports_native_tool_calling:
            raise ConfigurationError(
                f"Provider {provider_name} 不支持原生 function calling"
            )
        return provider_name, provider

    def _resolve_model_name(self, config_data: dict, provider_name: str, provider) -> str:
        """解析并校验模型名称。"""
        model_name = str(config_data["model"]).strip()
        if not provider.allow_custom_models and model_name not in provider.models:
            raise ConfigurationError(
                f"Provider {provider_name} 不支持模型: {model_name}"
            )
        return model_name
