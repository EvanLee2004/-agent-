"""DeerFlow 运行时资产服务。"""

import shutil
from pathlib import Path

from configuration.llm_configuration import LlmConfiguration
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets


# 运行时目录：DeerFlow 写入 checkpoint、memory.json 等可变状态的位置
DEERFLOW_RUNTIME_ROOT = Path(".runtime/deerflow")

# 静态配置目录：所有 DeerFlow 配置资产的唯一事实来源，提交到 git
DEERFLOW_STATIC_CONFIG_ROOT = Path(".agent_assets/deerflow_config")

# skills 根目录：提供给 DeerFlow 扫描 SKILL.md 的路径，通过 $DEER_FLOW_SKILLS_PATH 注入
DEERFLOW_SKILLS_ROOT = Path(".agent_assets/deerflow_skills")


class DeerFlowRuntimeAssetsService:
    """负责准备 DeerFlow 运行时所需的本地资产。

    当前职责仅剩两件事：
    1. 将静态 agent 配置文件（SOUL.md / config.yaml）从 .agent_assets/deerflow_config/
       同步到 DEER_FLOW_HOME/agents/，因为 DeerFlow 会往 DEER_FLOW_HOME 写 memory.json 等
       可变状态，不能直接指向 git 管理的静态目录。
    2. 构建运行时环境变量映射（API Key + DEER_FLOW_SKILLS_PATH），供调用方在执行前注入。

    所有 DeerFlow 主配置（config.yaml、extensions_config.json）已静态化，
    不再在运行时生成。config.yaml 中的 skills.path 使用 $DEER_FLOW_SKILLS_PATH
    占位符，由 DeerFlow 的 resolve_env_variables() 在读取时自动展开。
    """

    def __init__(
        self,
        role_catalog: FinanceDepartmentRoleCatalog,
        runtime_root: Path = DEERFLOW_RUNTIME_ROOT,
        skills_root: Path = DEERFLOW_SKILLS_ROOT,
        static_config_root: Path = DEERFLOW_STATIC_CONFIG_ROOT,
    ):
        self._role_catalog = role_catalog
        self._runtime_root = runtime_root
        self._skills_root = skills_root
        self._static_config_root = static_config_root

    def prepare_assets(self, configuration: LlmConfiguration) -> DeerFlowRuntimeAssets:
        """准备 DeerFlow 运行时资产。

        Args:
            configuration: 当前项目的 LLM 运行配置。

        Returns:
            DeerFlow 运行时需要的配置资产集合。
        """
        runtime_home = self._runtime_root / "home"
        runtime_home.mkdir(parents=True, exist_ok=True)

        # 将静态 agent 文件同步到运行时 home，使 DEER_FLOW_HOME/agents/<name>/ 始终最新
        self._sync_agent_files(runtime_home)

        return DeerFlowRuntimeAssets(
            runtime_root=self._runtime_root.resolve(),
            config_path=(self._static_config_root / "config.yaml").resolve(),
            extensions_config_path=(
                self._static_config_root / "extensions_config.json"
            ).resolve(),
            runtime_home=runtime_home.resolve(),
            available_skills=self._role_catalog.list_available_skill_names(),
            environment_variables=self._build_runtime_environment_variables(
                configuration
            ),
            runtime_configuration=configuration.runtime_configuration,
        )

    def _sync_agent_files(self, runtime_home: Path) -> None:
        """将静态 agent 配置文件同步到运行时 home/agents/ 目录。

        DeerFlow 从 DEER_FLOW_HOME/agents/<name>/ 读取 config.yaml 和 SOUL.md，
        但也会往 DEER_FLOW_HOME 写 memory.json 等运行时状态，因此不能直接把静态资产
        目录设为 DEER_FLOW_HOME。每次准备资产时做一次覆盖同步，确保 agent 配置始终
        与 .agent_assets/deerflow_config/home/agents/ 中的版本一致。
        """
        static_agents_dir = self._static_config_root / "home" / "agents"
        runtime_agents_dir = runtime_home / "agents"
        runtime_agents_dir.mkdir(exist_ok=True)

        for agent_src in static_agents_dir.iterdir():
            if not agent_src.is_dir():
                continue
            agent_dst = runtime_agents_dir / agent_src.name
            agent_dst.mkdir(exist_ok=True)
            for config_file in agent_src.iterdir():
                shutil.copy2(config_file, agent_dst / config_file.name)

    def _build_runtime_environment_variables(
        self,
        configuration: LlmConfiguration,
    ) -> dict[str, str]:
        """构造 DeerFlow 运行时需要注入的环境变量。

        包含两类变量：
        - 模型 API Key：config.yaml 里 api_key 字段写的是 $ENV_NAME 占位符，
          DeerFlow 读取配置时按名称从 os.environ 取真实密钥。
        - DEER_FLOW_SKILLS_PATH：config.yaml 的 skills.path 写的是
          $DEER_FLOW_SKILLS_PATH，DeerFlow 读配置时展开为 skills 根目录的绝对路径。
        """
        environment_variables: dict[str, str] = {}
        for model in configuration.list_models():
            environment_variables[model.api_key_env] = model.api_key
        environment_variables["DEER_FLOW_SKILLS_PATH"] = str(
            self._skills_root.resolve()
        )
        return environment_variables
