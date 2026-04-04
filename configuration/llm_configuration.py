"""LLM 配置集合。"""

from typing import Optional

from configuration.deerflow_runtime_configuration import DeerFlowRuntimeConfiguration
from configuration.llm_model_profile import LlmModelProfile


class LlmConfiguration:
    """描述当前项目可用的 LLM 模型池及默认模型。

    当前项目已经明确以 DeerFlow 的 `default_model + models[]` 结构为底座，因此这里
    不再保留单模型时代的兼容构造方式。这样做虽然会要求所有调用方都使用模型池结构，
    但能够确保运行时、配置文件、测试和文档围绕同一事实来源工作，不再长期背负过时分支。
    """

    def __init__(
        self,
        *,
        models: tuple[LlmModelProfile, ...],
        default_model_name: str,
        runtime_configuration: DeerFlowRuntimeConfiguration | None = None,
    ):
        # DeerFlow runtime 开关与模型池一样，都是“运行时事实”的一部分。
        # 这里在配置对象初始化时一次性固定下来，避免上层不同装配点各自维护默认值，
        # 造成 `config.yaml`、DeerFlowClient 和测试期望三处发生漂移。
        self._runtime_configuration = runtime_configuration or DeerFlowRuntimeConfiguration()
        self._models = self._build_models_from_pool(models)
        self._default_model_name = self._resolve_default_model_name(default_model_name, self._models)

    @property
    def default_model_name(self) -> str:
        """返回默认模型的稳定配置名。"""
        return self._default_model_name

    @property
    def runtime_configuration(self) -> DeerFlowRuntimeConfiguration:
        """返回 DeerFlow runtime 配置。

        之所以把 runtime 配置挂在统一配置对象上，而不是让运行时层自行读取零散字段，
        是为了保证“当前项目到底怎么启动 DeerFlow”只有一个事实来源。
        """
        return self._runtime_configuration

    def list_models(self) -> tuple[LlmModelProfile, ...]:
        """返回全部模型配置。"""
        return self._models

    def list_models_in_runtime_order(self) -> tuple[LlmModelProfile, ...]:
        """返回 DeerFlow 运行时应使用的模型顺序。

        DeerFlow 未显式指定 `model_name` 时会优先使用 `config.yaml` 中的第一条模型。
        因此这里必须把默认模型排到最前面，避免“配置里的默认模型”和 DeerFlow 实际
        选择的模型发生偏移。
        """
        default_model = self.get_default_model()
        remaining_models = [model for model in self._models if model.name != default_model.name]
        return (default_model, *remaining_models)

    def get_default_model(self) -> LlmModelProfile:
        """返回默认模型配置。"""
        default_model = self.get_model(self._default_model_name)
        if default_model is None:
            raise ValueError(f"未找到默认模型: {self._default_model_name}")
        return default_model

    def get_model(self, profile_name: str) -> Optional[LlmModelProfile]:
        """按稳定配置名获取模型配置。"""
        for model in self._models:
            if model.name == profile_name:
                return model
        return None

    def _build_models_from_pool(
        self,
        models: tuple[LlmModelProfile, ...],
    ) -> tuple[LlmModelProfile, ...]:
        """校验并冻结模型池。"""
        if not models:
            raise ValueError("models 不能为空")
        model_names: list[str] = []
        for model in models:
            if model.name in model_names:
                raise ValueError(f"模型名称重复: {model.name}")
            model_names.append(model.name)
        return models

    def _resolve_default_model_name(
        self,
        default_model_name: str,
        models: tuple[LlmModelProfile, ...],
    ) -> str:
        """解析默认模型名。"""
        if not any(model.name == default_model_name for model in models):
            raise ValueError(f"default_model_name 未出现在模型池中: {default_model_name}")
        return default_model_name
