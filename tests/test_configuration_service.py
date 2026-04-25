"""crewAI 配置服务测试。"""

import unittest

from configuration.configuration_error import ConfigurationError
from configuration.configuration_repository import ConfigurationRepository
from configuration.configuration_service import ConfigurationService
from configuration.crewai_runtime_configuration import CrewAIRuntimeConfiguration
from configuration.llm_configuration import LlmConfiguration
from configuration.llm_model_profile import LlmModelProfile
from configuration.provider_catalog import ProviderCatalog


class FakeConfigurationRepository(ConfigurationRepository):
    """测试用配置仓储。

    配置服务真正关心的是“配置结构如何被校验和规范化”，不是文件系统读写。
    用内存仓储可以让测试只覆盖配置契约，避免被 `.env` 或本地 config.json 干扰。
    """

    def __init__(self, config_data: dict | None = None):
        self.config_data = config_data
        self.saved_config_data: dict | None = None
        self.env_values = {"MINIMAX_API_KEY": "test-key"}

    def load_config_data(self) -> dict | None:
        """读取内存配置。"""
        return self.config_data

    def save_config_data(self, config_data: dict) -> None:
        """保存内存配置。"""
        self.saved_config_data = config_data

    def load_env_value(self, env_name: str) -> str:
        """读取测试环境变量。"""
        return self.env_values.get(env_name, "")

    def save_env_value(self, env_name: str, env_value: str) -> None:
        """保存测试环境变量。"""
        self.env_values[env_name] = env_value


def _build_config(runtime: dict | None = None) -> dict:
    """构造最小 crewAI 配置文档。"""
    config = {
        "default_model": "minimax",
        "models": [
            {
                "name": "minimax",
                "provider": "minimax",
                "model": "MiniMax-M1",
                "base_url": "https://api.minimax.chat/v1",
                "api_key_env": "MINIMAX_API_KEY",
            }
        ],
    }
    if runtime is not None:
        config["crewai_runtime"] = runtime
    return config


class ConfigurationServiceTest(unittest.TestCase):
    """验证配置层只暴露 crewAI runtime 契约。"""

    def test_loads_default_crewai_runtime_when_section_missing(self):
        """缺省 crewAI runtime 段时使用安全默认值。"""
        repository = FakeConfigurationRepository(_build_config())
        service = ConfigurationService(repository, ProviderCatalog())

        configuration = service.ensure_configuration()

        self.assertEqual(configuration.default_model_name, "minimax")
        self.assertEqual(configuration.get_default_model().model_name, "MiniMax-M1")
        self.assertEqual(
            configuration.runtime_configuration,
            CrewAIRuntimeConfiguration(
                process="sequential",
                memory_enabled=False,
                cache_enabled=False,
                verbose=False,
            ),
        )

    def test_rejects_non_sequential_process(self):
        """当前版本不接受 hierarchical 等动态流程。"""
        repository = FakeConfigurationRepository(
            _build_config({"process": "hierarchical"})
        )
        service = ConfigurationService(repository, ProviderCatalog())

        with self.assertRaises(ConfigurationError) as context:
            service.ensure_configuration()

        self.assertIn("crewai_runtime.process", str(context.exception))

    def test_saves_crewai_runtime_document(self):
        """保存配置时写出 crewAI runtime 段。"""
        repository = FakeConfigurationRepository()
        service = ConfigurationService(repository, ProviderCatalog())
        configuration = LlmConfiguration(
            models=(
                LlmModelProfile(
                    name="minimax",
                    provider_name="minimax",
                    model_name="MiniMax-M1",
                    base_url="https://api.minimax.chat/v1",
                    api_key_env="MINIMAX_API_KEY",
                    api_key="test-key",
                ),
            ),
            default_model_name="minimax",
            runtime_configuration=CrewAIRuntimeConfiguration(verbose=True),
        )

        service.save_configuration(configuration)

        self.assertIsNotNone(repository.saved_config_data)
        runtime_data = repository.saved_config_data["crewai_runtime"]
        self.assertEqual(runtime_data["process"], "sequential")
        self.assertFalse(runtime_data["memory_enabled"])
        self.assertFalse(runtime_data["cache_enabled"])
        self.assertTrue(runtime_data["verbose"])
        model_data = repository.saved_config_data["models"][0]
        self.assertNotIn("use", model_data)
        self.assertNotIn("supports_thinking", model_data)
        self.assertNotIn("supports_vision", model_data)
        self.assertNotIn("max_retries", model_data)


if __name__ == "__main__":
    unittest.main()
