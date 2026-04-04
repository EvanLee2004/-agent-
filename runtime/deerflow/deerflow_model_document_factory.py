"""DeerFlow 模型配置工厂。"""

from typing import Any

from configuration.llm_configuration import LlmConfiguration
from configuration.llm_model_profile import LlmModelProfile


MINIMAX_DEFAULT_TEMPERATURE = 1.0
DEFAULT_MODEL_TEMPERATURE = 0.7


class DeerFlowModelDocumentFactory:
    """负责构造 DeerFlow 模型配置文档。

    DeerFlow 原生配置支持 `models:` 列表，而不是单一模型。这里把模型文档生成收口到
    一处，是为了保证：

    1. 项目内部模型池可以无损投射到 DeerFlow `config.yaml`；
    2. 默认模型顺序与 DeerFlowClient 的默认选择保持一致；
    3. provider 特定默认值不会散落到运行时资产服务或配置服务。
    """

    def build_documents(self, configuration: LlmConfiguration) -> list[dict[str, Any]]:
        """构造全部模型配置文档。

        Args:
            configuration: 当前项目的模型池配置。

        Returns:
            可直接写入 DeerFlow `config.yaml` 的模型配置列表。
        """
        return [
            self._build_single_model_document(model)
            for model in configuration.list_models_in_runtime_order()
        ]

    def _build_single_model_document(self, model: LlmModelProfile) -> dict[str, Any]:
        """构造单条 DeerFlow 模型文档。"""
        return {
            "name": model.name,
            "display_name": model.get_display_name(),
            "use": model.use_path,
            "model": model.model_name,
            # DeerFlow 配置推荐使用环境变量占位，而不是把真实密钥直接写入 config.yaml。
            # 这样既和上游运行时约定一致，也避免把多个 provider 的真实密钥落盘。
            "api_key": f"${model.api_key_env}",
            "base_url": model.base_url,
            "request_timeout": model.request_timeout,
            "max_retries": model.max_retries,
            "max_tokens": model.max_tokens,
            "temperature": self._resolve_temperature(model),
            "supports_thinking": model.supports_thinking,
            "supports_vision": model.supports_vision,
        }

    def _resolve_temperature(self, model: LlmModelProfile) -> float:
        """解析模型温度。

        当前仍保留 provider 特定默认值，是因为 MiniMax 对 temperature 约束更严格，
        如果盲目统一成 0.7，很容易在运行时出现参数校验错误。
        """
        if model.temperature is not None:
            return model.temperature
        if model.provider_name == "minimax":
            return MINIMAX_DEFAULT_TEMPERATURE
        return DEFAULT_MODEL_TEMPERATURE
