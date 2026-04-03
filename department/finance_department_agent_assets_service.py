"""财务部门 DeerFlow 角色资产服务。"""

from pathlib import Path
from typing import Any

import yaml

from department.finance_department_role import FinanceDepartmentRole
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog


DEERFLOW_AGENT_DIRECTORY_NAME = "agents"
DEERFLOW_AGENT_CONFIG_FILE_NAME = "config.yaml"
DEERFLOW_AGENT_SOUL_FILE_NAME = "SOUL.md"


class FinanceDepartmentAgentAssetsService:
    """负责生成财务部门的 DeerFlow 角色资产。

    DeerFlow 允许通过 `${DEER_FLOW_HOME}/agents/<agent_name>/config.yaml` 与 `SOUL.md`
    加载自定义 agent。把这些文件生成职责固定在一个服务里，可以避免把角色配置散落到
    会话层、依赖容器和文档脚本中，也为后续角色扩展保留单一入口。
    """

    def __init__(self, role_catalog: FinanceDepartmentRoleCatalog):
        self._role_catalog = role_catalog

    def get_entry_role_name(self) -> str:
        """获取默认入口角色名。

        Returns:
            DeerFlow 主入口角色名。
        """
        return self._role_catalog.get_entry_role().agent_name

    def list_available_skill_names(self) -> set[str]:
        """获取运行时需要暴露的全部 skill。

        Returns:
            DeerFlow 运行时可见的技能集合。
        """
        return self._role_catalog.list_available_skill_names()

    def prepare_agent_assets(self, runtime_home: Path) -> None:
        """在 DeerFlow 运行目录下生成角色配置与 SOUL 资产。

        Args:
            runtime_home: DeerFlow 运行时 home 目录。
        """
        agents_root = runtime_home / DEERFLOW_AGENT_DIRECTORY_NAME
        agents_root.mkdir(parents=True, exist_ok=True)
        for role in self._role_catalog.list_roles():
            self._write_role_assets(agents_root, role)

    def _write_role_assets(self, agents_root: Path, role: FinanceDepartmentRole) -> None:
        """写入单个角色的配置与 SOUL。"""
        role_directory = agents_root / role.agent_name
        role_directory.mkdir(parents=True, exist_ok=True)
        config_path = role_directory / DEERFLOW_AGENT_CONFIG_FILE_NAME
        soul_path = role_directory / DEERFLOW_AGENT_SOUL_FILE_NAME
        config_path.write_text(
            yaml.safe_dump(
                self._build_agent_config_document(role),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        soul_path.write_text(role.soul_markdown.strip() + "\n", encoding="utf-8")

    def _build_agent_config_document(self, role: FinanceDepartmentRole) -> dict[str, Any]:
        """构造单个角色的 DeerFlow 配置文档。"""
        return {
            "name": role.agent_name,
            "description": role.description,
            "tool_groups": list(role.tool_groups),
            "skills": [
                *self._role_catalog.list_shared_skill_names(),
                *role.skill_names,
            ],
        }
