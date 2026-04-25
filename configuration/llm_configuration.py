"""LLM 配置集合。"""

from configuration.crewai_runtime_configuration import CrewAIRuntimeConfiguration
from configuration.llm_model_profile import LlmModelProfile


class LlmConfiguration:
    """描述当前项目可用的 LLM 模型池及默认模型。

    当前项目使用 crewAI 作为会计部门运行时，但模型配置继续保留
    `default_model + models[]` 结构。这样做不是为了兼容旧运行时，而是为了让
    多角色会计部门未来可以按角色或任务选择不同模型，同时避免再回到历史单模型配置。
    """

    def __init__(
        self,
        *,
        models: tuple[LlmModelProfile, ...],
        default_model_name: str,
        runtime_configuration: CrewAIRuntimeConfiguration | None = None,
    ):
        # crewAI runtime 开关与模型池一样，都是“运行时事实”的一部分。
        # 这里在配置对象初始化时一次性固定下来，避免上层不同装配点各自维护默认值。
        self._runtime_configuration = (
            runtime_configuration or CrewAIRuntimeConfiguration()
        )
        self._models = self._build_models_from_pool(models)
        self._default_model_name = self._resolve_default_model_name(
            default_model_name,
            self._models,
        )

    @property
    def default_model_name(self) -> str:
        """返回默认模型的稳定配置名。"""
        return self._default_model_name

    @property
    def runtime_configuration(self) -> CrewAIRuntimeConfiguration:
        """返回 crewAI runtime 配置。

        之所以把 runtime 配置挂在统一配置对象上，而不是让运行时层自行读取零散字段，
        是为了保证“当前项目到底怎么启动 crewAI 会计部门”只有一个事实来源。
        """
        return self._runtime_configuration

    def list_models(self) -> tuple[LlmModelProfile, ...]:
        """返回全部模型配置。"""
        return self._models

    def get_default_model(self) -> LlmModelProfile:
        """返回默认模型配置。"""
        default_model = self.get_model(self._default_model_name)
        if default_model is None:
            raise ValueError(f"未找到默认模型: {self._default_model_name}")
        return default_model

    def get_model(self, profile_name: str) -> LlmModelProfile | None:
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
