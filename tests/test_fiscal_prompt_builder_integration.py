"""FiscalRolePromptBuilder 集成测试——验证主链路真实消费 builder。

验证 GenerateFiscalTaskPromptRouter 作为自包含组件的正确性：
1. GenerateFiscalTaskPromptRouter 直接持有 FiscalRolePromptBuilder，无需外部服务注入
2. 工具上下文不包含 collaborate_with_department_role_router（legacy 工具已移除）
3. 静态 DeerFlow 工具配置不包含 collaborate_with_department_role（legacy 工具已移除）
4. 工具返回契约（纯 prompt 字符串）符合 DeerFlow task(prompt=...) 参数格式
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from department.collaboration.generate_fiscal_task_prompt_router import (
    GenerateFiscalTaskPromptRouter,
)
from department.subagent.fiscal_role_mode import FiscalRoleMode
from department.subagent.fiscal_role_prompt_builder import FiscalRolePromptBuilder

STATIC_CONFIG_PATH = Path(".agent_assets/deerflow_config/config.yaml")


class TestRouterIsSelfContained(unittest.TestCase):
    """验证 GenerateFiscalTaskPromptRouter 是自包含组件，直接持有 FiscalRolePromptBuilder。

    自包含设计：router 内部实例化 builder，不依赖外部服务注入。
    """

    def test_router_constructor_takes_no_arguments(self):
        """验证 router 构造函数无需参数。"""
        router = GenerateFiscalTaskPromptRouter()
        self.assertIsInstance(router, GenerateFiscalTaskPromptRouter)

    def test_router_holds_fiscal_role_prompt_builder(self):
        """验证 router 内部直接持有 builder 实例。"""
        router = GenerateFiscalTaskPromptRouter()
        self.assertIsInstance(router._prompt_builder, FiscalRolePromptBuilder)

    def test_router_directly_calls_builder(self):
        """验证路由直接调用 builder 生成 prompt，不经过外部服务。"""
        router = GenerateFiscalTaskPromptRouter()
        response = router.route({
            "fiscal_mode": "tax",
            "user_task": "计算企业所得税",
        })
        self.assertTrue(response.success)
        # TAX 模式的 prompt 包含"税务"
        self.assertIn("税务", response.payload["prompt"])


class TestAllFiveModes(unittest.TestCase):
    """验证五种专业模式都能通过 router 正确生成 prompt。"""

    def test_all_modes_return_non_empty_prompt(self):
        """验证每种模式都返回非空 prompt。"""
        router = GenerateFiscalTaskPromptRouter()
        for mode in FiscalRoleMode:
            response = router.route({"fiscal_mode": mode.value, "user_task": "测试任务"})
            self.assertTrue(response.success, f"{mode} 模式应成功")
            self.assertTrue(len(response.payload["prompt"]) > 0)

    def test_all_modes_produce_distinct_prompts(self):
        """验证五种模式产生不同的 prompt。"""
        router = GenerateFiscalTaskPromptRouter()
        bookkeeping = router.route({"fiscal_mode": "bookkeeping", "user_task": "记账"}).payload["prompt"]
        tax = router.route({"fiscal_mode": "tax", "user_task": "记账"}).payload["prompt"]
        self.assertIn("record_voucher", bookkeeping)
        self.assertIn("calculate_tax", tax)
        self.assertNotEqual(bookkeeping, tax)

    def test_tax_mode_contains_calculate_tax(self):
        """验证 TAX 模式包含 calculate_tax 工具。"""
        router = GenerateFiscalTaskPromptRouter()
        response = router.route({"fiscal_mode": "tax", "user_task": "测算增值税"})
        self.assertIn("calculate_tax", response.payload["prompt"])

    def test_bookkeeping_mode_restricts_tools(self):
        """验证 bookkeeping 模式工具边界约束。"""
        router = GenerateFiscalTaskPromptRouter()
        response = router.route({"fiscal_mode": "bookkeeping", "user_task": "录入报销"})
        prompt = response.payload["prompt"]
        self.assertIn("record_voucher", prompt)
        self.assertIn("## 权限边界", prompt)

    def test_context_appended_when_provided(self):
        """验证带 context 时上下文被附加到 prompt。"""
        router = GenerateFiscalTaskPromptRouter()
        response = router.route({
            "fiscal_mode": "tax",
            "user_task": "计算所得税",
            "context": "当前时间：2024年1月，已确认收入100万",
        })
        self.assertIn("## 已知上下文", response.payload["prompt"])
        self.assertIn("已确认收入100万", response.payload["prompt"])

    def test_invalid_fiscal_mode_returns_error(self):
        """验证不支持的 fiscal_mode 返回错误。"""
        router = GenerateFiscalTaskPromptRouter()
        response = router.route({"fiscal_mode": "invalid_mode", "user_task": "测试"})
        self.assertFalse(response.success)
        self.assertIn("不支持的专业模式", response.error_message)


class TestToolContextExcludesLegacyCollaboration(unittest.TestCase):
    """验证 FinanceDepartmentToolContext 不包含 legacy 协作路由。

    collaborate_with_department_role_router 已从工具上下文中移除（legacy 协作工具已废弃）。
    """

    def test_tool_context_has_no_collaborate_with_department_role_router(self):
        """验证工具上下文不包含 collaborate_with_department_role_router 字段。"""
        from runtime.deerflow.finance_department_tool_context import (
            FinanceDepartmentToolContext,
        )
        field_names = {f.name for f in FinanceDepartmentToolContext.__dataclass_fields__.values()}
        self.assertNotIn("collaborate_with_department_role_router", field_names)

    def test_tool_context_still_has_generate_fiscal_task_prompt_router(self):
        """验证工具上下文仍包含 generate_fiscal_task_prompt_router。"""
        from runtime.deerflow.finance_department_tool_context import (
            FinanceDepartmentToolContext,
        )
        field_names = {f.name for f in FinanceDepartmentToolContext.__dataclass_fields__.values()}
        self.assertIn("generate_fiscal_task_prompt_router", field_names)


class TestStaticToolConfigExcludesLegacyCollaboration(unittest.TestCase):
    """验证静态 DeerFlow 工具配置不包含 collaborate_with_department_role。

    legacy 协作工具已从静态 config.yaml 的 tools 段中移除。
    """

    def test_static_config_does_not_contain_legacy_collaboration_tool(self):
        """验证静态 config.yaml tools 段不包含 collaborate_with_department_role。"""
        config = yaml.safe_load(STATIC_CONFIG_PATH.read_text(encoding="utf-8"))
        tool_names = {tool["name"] for tool in config.get("tools", [])}
        self.assertNotIn("collaborate_with_department_role", tool_names)


class TestToolReturnContract(unittest.TestCase):
    """验证 generate_fiscal_task_prompt 工具的返回契约。

    关键约束：_run() 必须返回纯 prompt 字符串（不是 JSON 包装），
    这样才能无歧义地作为 DeerFlow task(prompt=...) 的参数。
    """

    def test_tool_run_returns_pure_string_not_json(self):
        """验证工具 _run() 返回纯字符串，不是 JSON 包装。"""
        from department.collaboration.generate_fiscal_task_prompt_tool import (
            GenerateFiscalTaskPromptTool,
        )
        from department.collaboration.generate_fiscal_task_prompt_router import (
            GenerateFiscalTaskPromptRouter,
        )
        from runtime.deerflow.finance_department_tool_context_registry import (
            FinanceDepartmentToolContextRegistry,
        )
        from runtime.deerflow.finance_department_tool_context import (
            FinanceDepartmentToolContext,
        )

        router = GenerateFiscalTaskPromptRouter()
        tool_context = FinanceDepartmentToolContext(
            record_voucher_router=MagicMock(),
            query_vouchers_router=MagicMock(),
            calculate_tax_router=MagicMock(),
            audit_voucher_router=MagicMock(),
            record_cash_transaction_router=MagicMock(),
            query_cash_transactions_router=MagicMock(),
            reply_with_rules_router=MagicMock(),
            generate_fiscal_task_prompt_router=router,
        )
        tool = GenerateFiscalTaskPromptTool()

        with FinanceDepartmentToolContextRegistry.open_context_scope(tool_context):
            result = tool._run(fiscal_mode="tax", user_task="计算企业所得税")

        self.assertIsInstance(result, str)
        self.assertNotIn('{"tool_name"', result)
        self.assertNotIn('"success"', result)
        self.assertNotIn('"payload"', result)
        self.assertIn("税务", result)  # TAX 模式 prompt 包含"税务"

    def test_tool_run_error_returns_error_text(self):
        """验证工具失败时返回错误文本，不是 JSON 包装。"""
        from department.collaboration.generate_fiscal_task_prompt_tool import (
            GenerateFiscalTaskPromptTool,
        )
        from department.collaboration.generate_fiscal_task_prompt_router import (
            GenerateFiscalTaskPromptRouter,
        )
        from runtime.deerflow.finance_department_tool_context_registry import (
            FinanceDepartmentToolContextRegistry,
        )
        from runtime.deerflow.finance_department_tool_context import (
            FinanceDepartmentToolContext,
        )

        router = GenerateFiscalTaskPromptRouter()
        tool_context = FinanceDepartmentToolContext(
            record_voucher_router=MagicMock(),
            query_vouchers_router=MagicMock(),
            calculate_tax_router=MagicMock(),
            audit_voucher_router=MagicMock(),
            record_cash_transaction_router=MagicMock(),
            query_cash_transactions_router=MagicMock(),
            reply_with_rules_router=MagicMock(),
            generate_fiscal_task_prompt_router=router,
        )
        tool = GenerateFiscalTaskPromptTool()

        with FinanceDepartmentToolContextRegistry.open_context_scope(tool_context):
            result = tool._run(fiscal_mode="invalid_mode", user_task="测试")

        self.assertIsInstance(result, str)
        self.assertNotIn('{"tool_name"', result)
        self.assertIn("生成 prompt 失败", result)
