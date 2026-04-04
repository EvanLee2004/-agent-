"""财务部门角色目录与 DeerFlow 资产测试。"""

import tempfile
import unittest
from pathlib import Path

import yaml

from department.finance_department_constants import DEERFLOW_BASE_TOOL_GROUP_NAMES
from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.roles.coordinator_role_definition import CoordinatorRoleDefinition
from runtime.deerflow.deerflow_tool_catalog import DeerFlowToolCatalog


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

    def test_coordinator_soul_matches_stage3_strategy(self):
        """验证 coordinator SOUL 与阶段 3 策略一致。

        阶段 3 策略：
        - 简单单步任务：直接使用财务工具
        - 复杂多步任务：先调 generate_fiscal_task_prompt 生成 prompt，再传给 DeerFlow task
        - collaborate_with_department_role：已从工具目录移除，SOUL 不再提及

        该测试确保 SOUL 文本与阶段 3 策略对齐。
        """
        role = CoordinatorRoleDefinition().build()
        soul = role.soul_markdown

        # 验证 generate_fiscal_task_prompt 工具出现在 SOUL 中
        self.assertIn("generate_fiscal_task_prompt", soul)

        # 验证 DeerFlow task 仍然被提及
        self.assertIn("task", soul.lower())
        self.assertIn("general-purpose", soul.lower())

        # 验证简单单步直接用工具的策略出现
        self.assertIn("record_voucher", soul)
        self.assertIn("calculate_tax", soul)

        # 阶段 3：collaborate_with_department_role 已移除，SOUL 不应再提及它
        self.assertNotIn("collaborate_with_department_role", soul)

    def test_tool_catalog_includes_generate_fiscal_task_prompt(self):
        """验证工具目录包含 generate_fiscal_task_prompt。"""
        catalog = DeerFlowToolCatalog()
        tool_names = {spec.name for spec in catalog.list_specs()}
        self.assertIn("generate_fiscal_task_prompt", tool_names)

    def test_tool_catalog_generate_fiscal_task_prompt_in_finance_group(self):
        """验证 generate_fiscal_task_prompt 属于 finance 工具组。"""
        from runtime.deerflow.deerflow_tool_spec import FINANCE_TOOL_GROUP_NAME

        catalog = DeerFlowToolCatalog()
        spec = next(s for s in catalog.list_specs() if s.name == "generate_fiscal_task_prompt")
        self.assertEqual(spec.group, FINANCE_TOOL_GROUP_NAME)

    def test_generated_config_yaml_contains_generate_fiscal_task_prompt(self):
        """验证 config.yaml tools 列表包含 generate_fiscal_task_prompt。

        tools 列表由 DeerFlowConfigDocumentFactory._build_tool_documents() 生成，
        直接来自 DeerFlowToolCatalog.list_specs()。这里通过检查 factory 输出验证。
        """
        from runtime.deerflow.deerflow_config_document_factory import (
            DeerFlowConfigDocumentFactory,
        )
        from runtime.deerflow.deerflow_model_document_factory import (
            DeerFlowModelDocumentFactory,
        )
        from runtime.deerflow.deerflow_tool_catalog import DeerFlowToolCatalog

        catalog = DeerFlowToolCatalog()
        factory = DeerFlowConfigDocumentFactory(
            DeerFlowModelDocumentFactory(),
            catalog,
        )
        # _build_tool_documents() 是 public 接口，直接测试其输出
        tool_docs = factory._build_tool_documents()
        tool_names = {t["name"] for t in tool_docs}
        self.assertIn("generate_fiscal_task_prompt", tool_names)
