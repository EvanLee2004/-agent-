"""配置服务测试。"""

import unittest

from configuration.configuration_error import ConfigurationError
from configuration.configuration_repository import ConfigurationRepository
from configuration.configuration_service import ConfigurationService
from configuration.deerflow_runtime_configuration import DeerFlowRuntimeConfiguration
from configuration.llm_configuration import LlmConfiguration
from configuration.llm_model_profile import LlmModelProfile
from configuration.provider_catalog import ProviderCatalog


class StubConfigurationRepository(ConfigurationRepository):
    """配置仓储测试替身。

    这里不直接依赖真实文件系统，是为了把测试目标聚焦在“配置校验与结构升级”本身，
    避免 `.env` 和 `config.json` 的读写细节把断言噪音带进来。
    """

    def __init__(
        self,
        config_data: dict | None = None,
        env_values: dict[str, str] | None = None,
    ):
        self._config_data = config_data
        self._env_values = env_values or {}
        self.saved_config_data: dict | None = None
        self.saved_env_values: dict[str, str] = {}

    def load_config_data(self) -> dict | None:
        """返回预设配置。"""
        return self._config_data

    def save_config_data(self, config_data: dict) -> None:
        """记录被保存的配置数据。"""
        self.saved_config_data = config_data

    def load_env_value(self, env_name: str) -> str:
        """返回预设环境变量值。"""
        return self._env_values.get(env_name, "")

    def save_env_value(self, env_name: str, env_value: str) -> None:
        """记录被保存的环境变量。"""
        self.saved_env_values[env_name] = env_value


class ConfigurationServiceTest(unittest.TestCase):
    """验证配置服务的当前结构校验与持久化行为。"""

    def test_ensure_configuration_rejects_legacy_single_model_config(self):
        """验证旧版单模型配置会被明确拒绝，而不是继续兼容。"""
        repository = StubConfigurationRepository(
            config_data={
                "provider": "minimax",
                "model": "MiniMax-M2.7",
                "base_url": "https://api.minimaxi.com/v1",
            },
        )
        service = ConfigurationService(repository, ProviderCatalog())

        with self.assertRaises(ConfigurationError):
            service.ensure_configuration()

    def test_ensure_configuration_loads_multi_model_and_runtime_options(self):
        """验证新版多模型配置与 DeerFlow runtime 配置都能正确加载。"""
        repository = StubConfigurationRepository(
            config_data={
                "default_model": "deepseek-research",
                "models": [
                    {
                        "name": "minimax-main",
                        "provider": "minimax",
                        "model": "MiniMax-M2.7",
                        "base_url": "https://api.minimaxi.com/v1",
                        "api_key_env": "MINIMAX_API_KEY",
                    },
                    {
                        "name": "deepseek-research",
                        "provider": "deepseek",
                        "model": "deepseek-reasoner",
                        "base_url": "https://api.deepseek.com/v1",
                        "api_key_env": "DEEPSEEK_API_KEY",
                        "supports_vision": False,
                    },
                ],
                "deerflow_runtime": {
                    "client": {
                        "thinking_enabled": False,
                        "subagent_enabled": True,
                        "plan_mode": True,
                    },
                    "tool_search": {
                        "enabled": True,
                    },
                    "sandbox": {
                        "use": "deerflow.sandbox.local:LocalSandboxProvider",
                        "allow_host_bash": True,
                        "bash_output_max_chars": 40000,
                        "read_file_output_max_chars": 80000,
                    },
                },
            },
            env_values={
                "MINIMAX_API_KEY": "minimax-key",
                "DEEPSEEK_API_KEY": "deepseek-key",
            },
        )
        service = ConfigurationService(repository, ProviderCatalog())

        configuration = service.ensure_configuration()

        self.assertEqual(configuration.default_model_name, "deepseek-research")
        self.assertEqual(
            [model.name for model in configuration.list_models_in_runtime_order()],
            ["deepseek-research", "minimax-main"],
        )
        self.assertEqual(
            configuration.runtime_configuration,
            DeerFlowRuntimeConfiguration(
                thinking_enabled=False,
                subagent_enabled=True,
                plan_mode=True,
                tool_search_enabled=True,
                sandbox_allow_host_bash=True,
                sandbox_bash_output_max_chars=40000,
                sandbox_read_file_output_max_chars=80000,
            ),
        )

    def test_ensure_configuration_rejects_missing_model_api_key(self):
        """验证任一已启用模型缺少密钥时会阻止启动。"""
        repository = StubConfigurationRepository(
            config_data={
                "default_model": "openai-main",
                "models": [
                    {
                        "name": "openai-main",
                        "provider": "openai",
                        "model": "gpt-4.1-mini",
                        "base_url": "https://api.openai.com/v1",
                        "api_key_env": "OPENAI_API_KEY",
                    },
                ],
            },
            env_values={},
        )
        service = ConfigurationService(repository, ProviderCatalog())

        with self.assertRaises(ConfigurationError):
            service.ensure_configuration()

    def test_save_configuration_persists_models_and_runtime_options(self):
        """验证保存配置时会写出 DeerFlow 风格模型池与 runtime 段。"""
        repository = StubConfigurationRepository()
        service = ConfigurationService(repository, ProviderCatalog())
        configuration = LlmConfiguration(
            models=(
                LlmModelProfile(
                    name="openai-main",
                    provider_name="openai",
                    model_name="gpt-4.1-mini",
                    base_url="https://api.openai.com/v1",
                    api_key_env="OPENAI_API_KEY",
                    api_key="openai-key",
                ),
            ),
            default_model_name="openai-main",
            runtime_configuration=DeerFlowRuntimeConfiguration(
                thinking_enabled=False,
                subagent_enabled=True,
                plan_mode=True,
                tool_search_enabled=True,
                sandbox_allow_host_bash=True,
            ),
        )

        service.save_configuration(configuration)

        self.assertEqual(repository.saved_config_data["default_model"], "openai-main")
        self.assertEqual(repository.saved_config_data["models"][0]["name"], "openai-main")
        self.assertEqual(
            repository.saved_config_data["deerflow_runtime"]["client"]["subagent_enabled"],
            True,
        )
        self.assertEqual(
            repository.saved_config_data["deerflow_runtime"]["tool_search"]["enabled"],
            True,
        )
        self.assertEqual(repository.saved_env_values["OPENAI_API_KEY"], "openai-key")
