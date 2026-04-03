"""DeerFlow 模型配置工厂。"""

from typing import Any

from configuration.llm_configuration import LlmConfiguration


MINIMAX_DEFAULT_TEMPERATURE = 1.0
DEFAULT_MODEL_TEMPERATURE = 0.7


class DeerFlowModelDocumentFactory:
    """负责构造 DeerFlow 单模型配置文档。

    模型配置属于 DeerFlow 运行时接入细节，不应该散落在运行时资产服务、依赖容器和
    文档脚本里。独立工厂能把 provider 差异和默认参数集中在一处维护。
    """

    def build(self, configuration: LlmConfiguration) -> dict[str, Any]:
        """构造单模型配置。

        Args:
            configuration: 当前项目的 LLM 运行配置。

        Returns:
            可直接写入 DeerFlow `config.yaml` 的模型配置字典。
        """
        return {
            "name": configuration.model_name,
            "display_name": configuration.model_name,
            "use": "langchain_openai:ChatOpenAI",
            "model": configuration.model_name,
            "api_key": "$LLM_API_KEY",
            "base_url": configuration.base_url,
            "request_timeout": 600.0,
            "max_retries": 2,
            "max_tokens": 4096,
            "temperature": self._resolve_temperature(configuration),
            "supports_thinking": True,
            "supports_vision": False,
        }

    def _resolve_temperature(self, configuration: LlmConfiguration) -> float:
        """按 provider 决定默认温度。

        当前保持 provider 特定默认值，是为了让运行时行为和上游接口约束保持一致，
        避免把“所有模型都按一个默认值处理”的假设写死到配置层。
        """
        if configuration.provider_name == "minimax":
            return MINIMAX_DEFAULT_TEMPERATURE
        return DEFAULT_MODEL_TEMPERATURE
