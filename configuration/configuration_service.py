"""配置服务。"""

from typing import Any

from configuration.configuration_error import ConfigurationError
from configuration.configuration_repository import ConfigurationRepository
from configuration.deerflow_runtime_configuration import DeerFlowRuntimeConfiguration
from configuration.llm_configuration import LlmConfiguration
from configuration.llm_model_profile import LlmModelProfile
from configuration.provider_catalog import ProviderCatalog
from configuration.provider_metadata import ProviderMetadata


MODEL_REQUIRED_KEYS = ("name", "provider", "model", "base_url", "api_key_env")


def _build_default_runtime_document() -> dict[str, Any]:
    """构造默认 DeerFlow runtime 文档。

    `deerflow_runtime` 段虽然允许省略，但运行时最终仍然必须拿到一套完整配置。
    这里集中提供默认值，避免 DeerFlow client 工厂、配置工厂和测试各自维护一份。
    """
    runtime_configuration = DeerFlowRuntimeConfiguration()
    return {
        "client": {
            "thinking_enabled": runtime_configuration.thinking_enabled,
            "subagent_enabled": runtime_configuration.subagent_enabled,
            "plan_mode": runtime_configuration.plan_mode,
        },
        "tool_search": {
            "enabled": runtime_configuration.tool_search_enabled,
        },
        "sandbox": {
            "use": runtime_configuration.sandbox_use_path,
            "allow_host_bash": runtime_configuration.sandbox_allow_host_bash,
            "bash_output_max_chars": runtime_configuration.sandbox_bash_output_max_chars,
            "read_file_output_max_chars": runtime_configuration.sandbox_read_file_output_max_chars,
        },
    }


class ConfigurationService:
    """配置服务。

    该服务负责把交互式配置、配置校验和配置恢复收敛到同一层，
    避免 CLI、LLM 网关和启动流程各自维护一套校验逻辑。

    当前阶段配置结构已经明确收口为 DeerFlow 风格的 `default_model + models[]`。
    因此这里不再接受历史单模型格式，避免配置层继续维持一条已经不打算长期保留的
    兼容路径。
    """

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
        model_profiles = tuple(
            self._build_model_profile(model_document)
            for model_document in normalized_config["models"]
        )
        return LlmConfiguration(
            models=model_profiles,
            default_model_name=normalized_config["default_model"],
            runtime_configuration=self._build_runtime_configuration(
                normalized_config["deerflow_runtime"]
            ),
        )

    def save_configuration(self, configuration: LlmConfiguration) -> None:
        """保存配置。

        Args:
            configuration: 已经确认过的运行配置。
        """
        self._configuration_repository.save_config_data(
            {
                "default_model": configuration.default_model_name,
                "models": [
                    self._build_persisted_model_document(model)
                    for model in configuration.list_models()
                ],
                "deerflow_runtime": self._build_persisted_runtime_document(
                    configuration.runtime_configuration
                ),
            }
        )
        for model in configuration.list_models():
            self._configuration_repository.save_env_value(
                model.api_key_env,
                model.api_key,
            )

    def _load_normalized_config(self) -> dict[str, Any]:
        """读取并校验配置文件。"""
        config_data = self._configuration_repository.load_config_data()
        if not config_data:
            raise ConfigurationError("缺少 config.json，请先完成模型配置")
        return self._validate_config_data(config_data)

    def _validate_config_data(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """校验并规范化配置字典。"""
        self._require_dict(config_data)
        if not isinstance(config_data.get("models"), list):
            raise ConfigurationError(
                "配置格式错误：当前版本只支持 DeerFlow 风格的 default_model + models[] 结构"
            )
        default_model_name = str(config_data.get("default_model") or "").strip()
        if not default_model_name:
            raise ConfigurationError("配置缺少必填字段: default_model")
        raw_models = config_data.get("models")
        if not isinstance(raw_models, list) or not raw_models:
            raise ConfigurationError("配置缺少可用模型列表: models")
        normalized_models = [
            self._validate_model_document(raw_model, index)
            for index, raw_model in enumerate(raw_models, start=1)
        ]
        model_names = [model["name"] for model in normalized_models]
        if default_model_name not in model_names:
            raise ConfigurationError(f"default_model 未出现在 models 中: {default_model_name}")
        return {
            "default_model": default_model_name,
            "models": normalized_models,
            "deerflow_runtime": self._validate_runtime_document(
                config_data.get("deerflow_runtime")
            ),
        }

    def _validate_model_document(
        self,
        raw_model: Any,
        index: int,
    ) -> dict[str, Any]:
        """校验单个模型文档。

        Args:
            raw_model: 原始模型配置对象。
            index: 模型在列表中的位置，供错误信息定位。

        Returns:
            通过校验的规范化模型配置。

        Raises:
            ConfigurationError: 模型配置不合法时抛出。
        """
        if not isinstance(raw_model, dict):
            raise ConfigurationError(f"models[{index}] 必须是对象")
        for key in MODEL_REQUIRED_KEYS:
            if not raw_model.get(key):
                raise ConfigurationError(f"models[{index}] 缺少必填字段: {key}")
        provider_name = str(raw_model["provider"]).strip()
        provider = self._resolve_provider(provider_name)
        model_name = self._resolve_model_name(
            provider_name=provider_name,
            provider=provider,
            raw_model=raw_model,
            index=index,
        )
        normalized_model = {
            "name": str(raw_model["name"]).strip(),
            "provider": provider_name,
            "model": model_name,
            "base_url": str(raw_model["base_url"]).strip(),
            "api_key_env": str(raw_model["api_key_env"]).strip(),
            "display_name": str(raw_model.get("display_name") or model_name).strip(),
            "use": str(raw_model.get("use") or "langchain_openai:ChatOpenAI").strip(),
            "supports_thinking": bool(raw_model.get("supports_thinking", True)),
            "supports_vision": bool(raw_model.get("supports_vision", False)),
            "request_timeout": float(raw_model.get("request_timeout", 600.0)),
            "max_retries": int(raw_model.get("max_retries", 2)),
            "max_tokens": int(raw_model.get("max_tokens", 4096)),
            "temperature": (
                float(raw_model["temperature"])
                if raw_model.get("temperature") is not None
                else None
            ),
        }
        if not normalized_model["name"]:
            raise ConfigurationError(f"models[{index}] 的 name 不能为空")
        if not normalized_model["api_key_env"]:
            raise ConfigurationError(f"models[{index}] 的 api_key_env 不能为空")
        return normalized_model

    def _build_model_profile(self, model_document: dict[str, Any]) -> LlmModelProfile:
        """把规范化模型文档转换为运行期模型配置。"""
        api_key_env = model_document["api_key_env"]
        api_key = self._configuration_repository.load_env_value(api_key_env)
        if not api_key:
            raise ConfigurationError(
                f"缺少模型 {model_document['name']} 所需的环境变量: {api_key_env}"
            )
        return LlmModelProfile(
            name=model_document["name"],
            provider_name=model_document["provider"],
            model_name=model_document["model"],
            base_url=model_document["base_url"],
            api_key_env=api_key_env,
            api_key=api_key,
            display_name=model_document["display_name"],
            use_path=model_document["use"],
            supports_thinking=model_document["supports_thinking"],
            supports_vision=model_document["supports_vision"],
            request_timeout=model_document["request_timeout"],
            max_retries=model_document["max_retries"],
            max_tokens=model_document["max_tokens"],
            temperature=model_document["temperature"],
        )

    def _build_persisted_model_document(self, model: LlmModelProfile) -> dict[str, Any]:
        """把运行期模型配置转换为可持久化结构。"""
        return {
            "name": model.name,
            "provider": model.provider_name,
            "model": model.model_name,
            "base_url": model.base_url,
            "api_key_env": model.api_key_env,
            "display_name": model.get_display_name(),
            "use": model.use_path,
            "supports_thinking": model.supports_thinking,
            "supports_vision": model.supports_vision,
            "request_timeout": model.request_timeout,
            "max_retries": model.max_retries,
            "max_tokens": model.max_tokens,
            "temperature": model.temperature,
        }

    def _build_runtime_configuration(
        self,
        runtime_document: dict[str, Any],
    ) -> DeerFlowRuntimeConfiguration:
        """把规范化 DeerFlow runtime 文档转换为运行期对象。"""
        client_document = runtime_document["client"]
        tool_search_document = runtime_document["tool_search"]
        sandbox_document = runtime_document["sandbox"]
        return DeerFlowRuntimeConfiguration(
            thinking_enabled=client_document["thinking_enabled"],
            subagent_enabled=client_document["subagent_enabled"],
            plan_mode=client_document["plan_mode"],
            tool_search_enabled=tool_search_document["enabled"],
            sandbox_use_path=sandbox_document["use"],
            sandbox_allow_host_bash=sandbox_document["allow_host_bash"],
            sandbox_bash_output_max_chars=sandbox_document["bash_output_max_chars"],
            sandbox_read_file_output_max_chars=sandbox_document["read_file_output_max_chars"],
        )

    def _build_persisted_runtime_document(
        self,
        runtime_configuration: DeerFlowRuntimeConfiguration,
    ) -> dict[str, Any]:
        """把运行期 DeerFlow runtime 配置转换为可持久化结构。"""
        return {
            "client": {
                "thinking_enabled": runtime_configuration.thinking_enabled,
                "subagent_enabled": runtime_configuration.subagent_enabled,
                "plan_mode": runtime_configuration.plan_mode,
            },
            "tool_search": {
                "enabled": runtime_configuration.tool_search_enabled,
            },
            "sandbox": {
                "use": runtime_configuration.sandbox_use_path,
                "allow_host_bash": runtime_configuration.sandbox_allow_host_bash,
                "bash_output_max_chars": runtime_configuration.sandbox_bash_output_max_chars,
                "read_file_output_max_chars": runtime_configuration.sandbox_read_file_output_max_chars,
            },
        }

    def _require_dict(self, config_data: dict[str, Any]) -> None:
        """校验配置必须是字典对象。"""
        if not isinstance(config_data, dict):
            raise ConfigurationError("配置格式错误：config.json 必须是对象")

    def _validate_runtime_document(self, raw_runtime: Any) -> dict[str, Any]:
        """校验 DeerFlow runtime 配置。

        这里允许 `deerflow_runtime` 整段缺失，因为老配置文件还没有这个结构。
        但一旦用户显式提供了该字段，就必须保证它能无损映射到 DeerFlow client
        参数和 `config.yaml` 的对应段，避免出现“配置里写了开关但运行时没吃到”的假象。
        """
        if raw_runtime is None:
            return _build_default_runtime_document()
        if not isinstance(raw_runtime, dict):
            raise ConfigurationError("deerflow_runtime 必须是对象")
        raw_client_document = raw_runtime.get("client")
        raw_tool_search_document = raw_runtime.get("tool_search")
        raw_sandbox_document = raw_runtime.get("sandbox")
        if raw_client_document is not None and not isinstance(raw_client_document, dict):
            raise ConfigurationError("deerflow_runtime.client 必须是对象")
        if raw_tool_search_document is not None and not isinstance(raw_tool_search_document, dict):
            raise ConfigurationError("deerflow_runtime.tool_search 必须是对象")
        if raw_sandbox_document is not None and not isinstance(raw_sandbox_document, dict):
            raise ConfigurationError("deerflow_runtime.sandbox 必须是对象")
        default_runtime_document = _build_default_runtime_document()
        default_client_document = default_runtime_document["client"]
        default_tool_search_document = default_runtime_document["tool_search"]
        default_sandbox_document = default_runtime_document["sandbox"]
        client_document = raw_client_document or {}
        tool_search_document = raw_tool_search_document or {}
        sandbox_document = raw_sandbox_document or {}
        return {
            "client": {
                "thinking_enabled": self._read_bool_field(
                    client_document,
                    "thinking_enabled",
                    default_client_document["thinking_enabled"],
                    "deerflow_runtime.client",
                ),
                "subagent_enabled": self._read_bool_field(
                    client_document,
                    "subagent_enabled",
                    default_client_document["subagent_enabled"],
                    "deerflow_runtime.client",
                ),
                "plan_mode": self._read_bool_field(
                    client_document,
                    "plan_mode",
                    default_client_document["plan_mode"],
                    "deerflow_runtime.client",
                ),
            },
            "tool_search": {
                "enabled": self._read_bool_field(
                    tool_search_document,
                    "enabled",
                    default_tool_search_document["enabled"],
                    "deerflow_runtime.tool_search",
                ),
            },
            "sandbox": {
                "use": self._read_string_field(
                    sandbox_document,
                    "use",
                    default_sandbox_document["use"],
                    "deerflow_runtime.sandbox",
                ),
                "allow_host_bash": self._read_bool_field(
                    sandbox_document,
                    "allow_host_bash",
                    default_sandbox_document["allow_host_bash"],
                    "deerflow_runtime.sandbox",
                ),
                "bash_output_max_chars": self._read_int_field(
                    sandbox_document,
                    "bash_output_max_chars",
                    default_sandbox_document["bash_output_max_chars"],
                    "deerflow_runtime.sandbox",
                ),
                "read_file_output_max_chars": self._read_int_field(
                    sandbox_document,
                    "read_file_output_max_chars",
                    default_sandbox_document["read_file_output_max_chars"],
                    "deerflow_runtime.sandbox",
                ),
            },
        }

    def _read_bool_field(
        self,
        document: dict[str, Any],
        field_name: str,
        default_value: bool,
        section_name: str,
    ) -> bool:
        """读取布尔字段并保持类型明确。

        这里不接受 `"true"` / `"false"` 这类字符串，是因为 JSON 本身原生支持布尔值。
        如果继续默默做字符串兼容，后面定位配置错误会非常困难。
        """
        if field_name not in document:
            return default_value
        field_value = document[field_name]
        if not isinstance(field_value, bool):
            raise ConfigurationError(f"{section_name}.{field_name} 必须是布尔值")
        return field_value

    def _read_int_field(
        self,
        document: dict[str, Any],
        field_name: str,
        default_value: int,
        section_name: str,
    ) -> int:
        """读取整数配置并拒绝布尔值冒充整数。"""
        if field_name not in document:
            return default_value
        field_value = document[field_name]
        if isinstance(field_value, bool) or not isinstance(field_value, int):
            raise ConfigurationError(f"{section_name}.{field_name} 必须是整数")
        return field_value

    def _read_string_field(
        self,
        document: dict[str, Any],
        field_name: str,
        default_value: str,
        section_name: str,
    ) -> str:
        """读取字符串字段并确保非空。"""
        if field_name not in document:
            return default_value
        field_value = str(document[field_name]).strip()
        if not field_value:
            raise ConfigurationError(f"{section_name}.{field_name} 不能为空")
        return field_value

    def _resolve_provider(self, provider_name: str) -> ProviderMetadata:
        """解析并校验 provider。"""
        provider = self._provider_catalog.get_provider(provider_name)
        if provider is None:
            raise ConfigurationError(f"不支持的 provider: {provider_name}")
        if not provider.supports_tool_calling:
            raise ConfigurationError(f"Provider {provider_name} 不支持工具调用")
        return provider

    def _resolve_model_name(
        self,
        *,
        provider_name: str,
        provider: ProviderMetadata,
        raw_model: dict[str, Any],
        index: int,
    ) -> str:
        """解析并校验模型名称。"""
        model_name = str(raw_model["model"]).strip()
        if not provider.allow_custom_models and model_name not in provider.models:
            raise ConfigurationError(
                f"models[{index}] 的 provider {provider_name} 不支持模型: {model_name}"
            )
        return model_name
