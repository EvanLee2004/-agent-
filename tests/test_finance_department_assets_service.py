"""财务部门角色目录与静态 DeerFlow 资产测试。"""

import unittest
from pathlib import Path

import yaml

from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog

STATIC_CONFIG_ROOT = Path(".agent_assets/deerflow_config")
STATIC_AGENTS_DIR = STATIC_CONFIG_ROOT / "home" / "agents"
EXPECTED_BASE_TOOL_GROUP_NAMES = ["web", "file:read", "file:write", "bash", "finance"]
EXPECTED_TOOL_NAMES = {
    "web_search",
    "web_fetch",
    "image_search",
    "ls",
    "read_file",
    "write_file",
    "str_replace",
    "bash",
    "record_voucher",
    "query_vouchers",
    "record_cash_transaction",
    "query_cash_transactions",
    "calculate_tax",
    "audit_voucher",
    "reply_with_rules",
    "generate_fiscal_task_prompt",
}


class FinanceDepartmentRoleCatalogTest(unittest.TestCase):
    """验证财务部门角色目录。"""

    def test_exposes_entry_role_and_all_skills(self):
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


class StaticAgentAssetsTest(unittest.TestCase):
    """验证 .agent_assets/deerflow_config/ 中的静态 agent 资产完整性。

    这些文件是 DeerFlow agent 的唯一配置事实来源，不再通过 Python 服务在运行时生成。
    """

    def test_all_six_agent_directories_exist(self):
        """验证六个角色各自拥有独立的资产目录。"""
        expected_agents = {
            "finance-coordinator",
            "finance-bookkeeping",
            "finance-cashier",
            "finance-audit",
            "finance-tax",
            "finance-policy-research",
        }
        actual_agents = {d.name for d in STATIC_AGENTS_DIR.iterdir() if d.is_dir()}
        self.assertEqual(actual_agents, expected_agents)

    def test_each_agent_has_config_and_soul_files(self):
        """验证每个角色目录包含 config.yaml 和 SOUL.md。"""
        for agent_dir in STATIC_AGENTS_DIR.iterdir():
            if not agent_dir.is_dir():
                continue
            with self.subTest(agent=agent_dir.name):
                self.assertTrue(
                    (agent_dir / "config.yaml").exists(),
                    f"{agent_dir.name} 缺少 config.yaml",
                )
                self.assertTrue(
                    (agent_dir / "SOUL.md").exists(),
                    f"{agent_dir.name} 缺少 SOUL.md",
                )

    def test_coordinator_config_has_correct_tool_groups_and_skills(self):
        """验证 coordinator config.yaml 工具组与技能列表正确。"""
        coordinator_config = yaml.safe_load(
            (STATIC_AGENTS_DIR / "finance-coordinator" / "config.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            coordinator_config["tool_groups"],
            EXPECTED_BASE_TOOL_GROUP_NAMES,
        )
        self.assertEqual(coordinator_config["skills"], ["finance-core", "coordinator"])

    def test_coordinator_soul_matches_collaboration_strategy(self):
        """验证 coordinator SOUL.md 内容与当前协作策略一致。

        当前协作策略（长期有效）：
        - 简单单步任务：直接使用财务工具
        - 复杂多步任务：先调 generate_fiscal_task_prompt，再传给 DeerFlow task
        - collaborate_with_department_role：已移除，SOUL 不应提及
        """
        soul = (STATIC_AGENTS_DIR / "finance-coordinator" / "SOUL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("generate_fiscal_task_prompt", soul)
        self.assertIn("task", soul.lower())
        self.assertIn("general-purpose", soul.lower())
        self.assertIn("record_voucher", soul)
        self.assertIn("calculate_tax", soul)
        self.assertNotIn("collaborate_with_department_role", soul)

    def test_static_config_yaml_has_env_var_skills_path(self):
        """验证 config.yaml 的 skills.path 使用 $DEER_FLOW_SKILLS_PATH 占位符。

        绝对路径不能写入 git 跟踪的静态文件，必须通过环境变量占位符注入。
        """
        config = yaml.safe_load(
            (STATIC_CONFIG_ROOT / "config.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(config["skills"]["path"], "$DEER_FLOW_SKILLS_PATH")

    def test_static_config_yaml_has_no_checkpointer_section(self):
        """验证 config.yaml 不含 checkpointer 段（由工厂程序化注入）。"""
        config = yaml.safe_load(
            (STATIC_CONFIG_ROOT / "config.yaml").read_text(encoding="utf-8")
        )
        self.assertNotIn("checkpointer", config)


class StaticToolConfigTest(unittest.TestCase):
    """验证静态 DeerFlow 工具配置完整性。

    当前工具定义的唯一事实来源是 .agent_assets/deerflow_config/config.yaml，
    不再保留 Python 侧的 DeerFlowToolCatalog 双写副本。
    """

    def test_config_yaml_includes_generate_fiscal_task_prompt(self):
        """验证静态 config.yaml 包含 generate_fiscal_task_prompt。"""
        config = yaml.safe_load(
            (STATIC_CONFIG_ROOT / "config.yaml").read_text(encoding="utf-8")
        )
        tool_names = {tool["name"] for tool in config.get("tools", [])}
        self.assertIn("generate_fiscal_task_prompt", tool_names)

    def test_generate_fiscal_task_prompt_in_finance_group(self):
        """验证 generate_fiscal_task_prompt 属于 finance 工具组。"""
        config = yaml.safe_load(
            (STATIC_CONFIG_ROOT / "config.yaml").read_text(encoding="utf-8")
        )
        target_tool = next(
            tool for tool in config.get("tools", []) if tool["name"] == "generate_fiscal_task_prompt"
        )
        self.assertEqual(target_tool["group"], "finance")

    def test_static_config_yaml_contains_all_expected_tools(self):
        """验证静态 config.yaml 覆盖当前全部预期工具名。"""

        config = yaml.safe_load(
            (STATIC_CONFIG_ROOT / "config.yaml").read_text(encoding="utf-8")
        )
        static_tool_names = {t["name"] for t in config.get("tools", [])}

        self.assertEqual(
            static_tool_names,
            EXPECTED_TOOL_NAMES,
            "静态 config.yaml tools 段与当前预期工具集不一致，请同步更新",
        )
