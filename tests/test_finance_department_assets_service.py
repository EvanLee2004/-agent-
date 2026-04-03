"""财务部门角色目录与 DeerFlow 资产测试。"""

import tempfile
import unittest
from pathlib import Path

import yaml

from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog


class FinanceDepartmentAssetsServiceTest(unittest.TestCase):
    """验证财务部门角色目录和 DeerFlow 角色资产。"""

    def test_role_catalog_exposes_entry_role_and_all_skills(self):
        """验证角色目录能提供入口角色和完整 skill 集合。"""
        role_catalog = FinanceDepartmentRoleCatalog()

        self.assertEqual(role_catalog.get_entry_role().agent_name, "finance-coordinator")
        self.assertEqual(role_catalog.get_department_display_name(), "智能财务部门")
        self.assertEqual(
            role_catalog.list_available_skill_names(),
            {
                "finance-core",
                "coordinator",
                "bookkeeping",
                "policy-research",
                "tax",
                "audit",
            },
        )

    def test_agent_assets_service_writes_all_role_configs(self):
        """验证角色资产服务会为五个角色生成配置和 SOUL。"""
        role_catalog = FinanceDepartmentRoleCatalog()
        assets_service = FinanceDepartmentAgentAssetsService(role_catalog)

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_home = Path(temp_dir) / "home"
            assets_service.prepare_agent_assets(runtime_home)

            coordinator_directory = runtime_home / "agents" / "finance-coordinator"
            bookkeeping_directory = runtime_home / "agents" / "finance-bookkeeping"
            audit_directory = runtime_home / "agents" / "finance-audit"

            self.assertTrue((coordinator_directory / "config.yaml").exists())
            self.assertTrue((bookkeeping_directory / "config.yaml").exists())
            self.assertTrue((audit_directory / "SOUL.md").exists())

            coordinator_config = yaml.safe_load(
                (coordinator_directory / "config.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(coordinator_config["skills"], ["finance-core", "coordinator"])
            self.assertEqual(coordinator_config["tool_groups"], ["finance"])
