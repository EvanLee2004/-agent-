"""DeerFlow 运行时资产服务。"""

import json
from pathlib import Path

import yaml

from configuration.llm_configuration import LlmConfiguration
from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from runtime.deerflow.deerflow_config_document_factory import DeerFlowConfigDocumentFactory
from runtime.deerflow.deerflow_extensions_document_factory import DeerFlowExtensionsDocumentFactory
from runtime.deerflow.deerflow_model_document_factory import DeerFlowModelDocumentFactory
from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets
from runtime.deerflow.deerflow_tool_catalog import DeerFlowToolCatalog


DEERFLOW_RUNTIME_ROOT = Path(".runtime/deerflow")
DEERFLOW_CONFIG_FILE_NAME = "config.yaml"
DEERFLOW_EXTENSIONS_FILE_NAME = "extensions_config.json"
DEERFLOW_CHECKPOINT_FILE_NAME = "checkpoints.sqlite"
DEERFLOW_HOME_DIRECTORY_NAME = "home"
DEERFLOW_SKILLS_ROOT = Path(".agent_assets/deerflow_skills")


class DeerFlowRuntimeAssetsService:
    """负责准备 DeerFlow 运行时所需的本地资产。

    我们把 DeerFlow 当作外部底层引擎使用，因此配置文件、扩展文件和
    skills 路径都不应该散落在 CLI、依赖容器或业务代码里。把它们集中到
    一个服务，是为了保证运行时接入只有一个事实来源，后续切多 Agent 时
    也不需要在多个位置同步改配置结构。
    """

    def __init__(
        self,
        department_agent_assets_service: FinanceDepartmentAgentAssetsService,
        runtime_root: Path = DEERFLOW_RUNTIME_ROOT,
        skills_root: Path = DEERFLOW_SKILLS_ROOT,
    ):
        self._department_agent_assets_service = department_agent_assets_service
        self._runtime_root = runtime_root
        self._skills_root = skills_root
        self._available_skills = self._department_agent_assets_service.list_available_skill_names()
        self._config_document_factory = DeerFlowConfigDocumentFactory(
            DeerFlowModelDocumentFactory(),
            DeerFlowToolCatalog(),
        )
        self._extensions_document_factory = DeerFlowExtensionsDocumentFactory()

    def prepare_assets(self, configuration: LlmConfiguration) -> DeerFlowRuntimeAssets:
        """准备 DeerFlow 运行时资产。

        Args:
            configuration: 当前项目的 LLM 运行配置。

        Returns:
            DeerFlow 运行时需要的配置资产集合。
        """
        self._runtime_root.mkdir(parents=True, exist_ok=True)
        runtime_home = self._runtime_root / DEERFLOW_HOME_DIRECTORY_NAME
        runtime_home.mkdir(parents=True, exist_ok=True)
        self._department_agent_assets_service.prepare_agent_assets(runtime_home)
        config_path = self._runtime_root / DEERFLOW_CONFIG_FILE_NAME
        extensions_config_path = self._runtime_root / DEERFLOW_EXTENSIONS_FILE_NAME
        checkpoint_path = self._runtime_root / DEERFLOW_CHECKPOINT_FILE_NAME
        config_path.write_text(
            yaml.safe_dump(
                self._config_document_factory.build(
                    configuration=configuration,
                    checkpoint_path=checkpoint_path,
                    skills_root=self._skills_root,
                ),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        extensions_config_path.write_text(
            json.dumps(
                self._extensions_document_factory.build(set(self._available_skills)),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return DeerFlowRuntimeAssets(
            runtime_root=self._runtime_root.resolve(),
            config_path=config_path,
            extensions_config_path=extensions_config_path,
            runtime_home=runtime_home.resolve(),
            skills_path=self._skills_root.resolve(),
            available_skills=set(self._available_skills),
            environment_variables=self._build_runtime_environment_variables(configuration),
            runtime_configuration=configuration.runtime_configuration,
        )

    def _build_runtime_environment_variables(
        self,
        configuration: LlmConfiguration,
    ) -> dict[str, str]:
        """构造 DeerFlow 运行时所需的环境变量映射。

        现在配置层已经支持多模型，因此运行时不能再只注入单个 `LLM_API_KEY`。
        DeerFlow 会在解析每个模型条目时按 `api_key: $ENV_NAME` 读取环境变量，
        所以这里必须把所有已启用模型对应的密钥都注入进去，才能保证任一模型被选中时
        都能正常启动。
        """
        environment_variables: dict[str, str] = {}
        for model in configuration.list_models():
            environment_variables[model.api_key_env] = model.api_key
        return environment_variables
