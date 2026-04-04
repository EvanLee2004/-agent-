"""财务部门角色目录与 DeerFlow 资产测试。"""

import tempfile
import unittest
from pathlib import Path

import yaml

from department.finance_department_constants import DEERFLOW_BASE_TOOL_GROUP_NAMES
from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.roles.coordinator_role_definition import CoordinatorRoleDefinition


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
                "cashier",
                "bookkeeping",
                "policy-research",
                "tax",
                "audit",
            },
        )

    def test_agent_assets_service_writes_all_role_configs(self):
        """验证角色资产服务会为六个角色生成配置和 SOUL。"""
        role_catalog = FinanceDepartmentRoleCatalog()
        assets_service = FinanceDepartmentAgentAssetsService(role_catalog)

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_home = Path(temp_dir) / "home"
            assets_service.prepare_agent_assets(runtime_home)

            coordinator_directory = runtime_home / "agents" / "finance-coordinator"
            cashier_directory = runtime_home / "agents" / "finance-cashier"
            bookkeeping_directory = runtime_home / "agents" / "finance-bookkeeping"
            audit_directory = runtime_home / "agents" / "finance-audit"

            self.assertTrue((coordinator_directory / "config.yaml").exists())
            self.assertTrue((cashier_directory / "config.yaml").exists())
            self.assertTrue((bookkeeping_directory / "config.yaml").exists())
            self.assertTrue((audit_directory / "SOUL.md").exists())

            coordinator_config = yaml.safe_load(
                (coordinator_directory / "config.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(coordinator_config["skills"], ["finance-core", "coordinator"])
            self.assertEqual(
                coordinator_config["tool_groups"],
                list(DEERFLOW_BASE_TOOL_GROUP_NAMES),
            )

    def test_coordinator_soul_matches_stage1_strategy(self):
        """验证 coordinator SOUL 与阶段 1 策略一致，不再优先使用 collaborate_with_department_role。

        阶段 1 策略：
        - 简单单步任务：直接使用财务工具
        - 复杂多步任务：优先使用 DeerFlow 原生 task(subagent_type="general-purpose")
        - collaborate_with_department_role：仅 legacy fallback

        该测试确保 SOUL 文本与上述策略对齐，防止旧策略（优先 collaborate_with_department_role）
        通过 SOUL 残留渗透到运行时提示中。
        """
        role = CoordinatorRoleDefinition().build()
        soul = role.soul_markdown

        # 验证阶段 1 核心策略出现在 SOUL 中
        self.assertIn("task", soul.lower())
        self.assertIn("general-purpose", soul.lower())

        # 验证简单单步直接用工具的策略出现
        self.assertIn("record_voucher", soul)
        self.assertIn("calculate_tax", soul)

        # 验证 legacy fallback 表述存在
        self.assertIn("Legacy fallback", soul)
        self.assertIn("collaborate_with_department_role", soul)

        # 验证 SOUL 中没有"优先使用 collaborate_with_department_role"这类旧口径
        # 注意：SOUL 中可以出现 collaborate_with_department_role（作为 legacy 说明），
        # 但不能出现"优先"或类似表示它是默认路径的表述
        self.assertNotIn("优先使用 collaborate_with_department_role", soul)
        self.assertNotIn("优先使用collaborate_with_department_role", soul)
