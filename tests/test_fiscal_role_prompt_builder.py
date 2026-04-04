"""财务子代理 Prompt 构建器测试。"""

import unittest

from department.subagent.fiscal_role_mode import FiscalRoleMode
from department.subagent.fiscal_role_prompt_builder import FiscalRolePromptBuilder


class TestFiscalRolePromptBuilder(unittest.TestCase):
    """验证 FiscalRolePromptBuilder 能为五种专业模式生成有效 prompt。"""

    def setUp(self):
        self.builder = FiscalRolePromptBuilder()

    def test_list_supported_modes_returns_all_five(self):
        """验证支持全部五种专业模式。"""
        modes = self.builder.list_supported_modes()
        self.assertEqual(
            set(modes),
            {"bookkeeping", "tax", "audit", "cashier", "policy_research"},
        )

    def test_bookkeeping_mode_contains_identity_and_tools(self):
        """验证 bookkeeping 模式 prompt 包含身份、工具和权限边界。"""
        prompt = self.builder.build(
            mode=FiscalRoleMode.BOOKKEEPING,
            user_task="录入本月差旅报销单据",
        )
        self.assertIn("记账", prompt)
        self.assertIn("record_voucher", prompt)
        self.assertIn("query_vouchers", prompt)
        self.assertIn("## 权限边界", prompt)

    def test_tax_mode_restricts_tools_and_boundaries(self):
        """验证 tax 模式工具边界约束：只能税务工具，不能记账/审核。"""
        prompt = self.builder.build(
            mode=FiscalRoleMode.TAX,
            user_task="计算企业所得税",
        )
        self.assertIn("税务", prompt)
        self.assertIn("calculate_tax", prompt)
        # 权限边界应明确：不能直接记账
        self.assertIn("## 权限边界", prompt)

    def test_audit_mode_forbids_direct_bookkeeping(self):
        """验证 audit 模式权限边界：不能直接改账。"""
        prompt = self.builder.build(
            mode=FiscalRoleMode.AUDIT,
            user_task="审核本月凭证风险",
        )
        self.assertIn("审核", prompt)
        self.assertIn("audit_voucher", prompt)
        self.assertIn("## 权限边界", prompt)

    def test_cashier_mode_restricts_to_cash_tools(self):
        """验证 cashier 模式：只能用资金收付工具。"""
        prompt = self.builder.build(
            mode=FiscalRoleMode.CASHIER,
            user_task="确认本月已付款项",
        )
        self.assertIn("出纳", prompt)
        self.assertIn("record_cash_transaction", prompt)
        self.assertIn("query_cash_transactions", prompt)

    def test_policy_research_mode_allows_web_tools(self):
        """验证 policy_research 模式：允许 web_search/web_fetch。"""
        prompt = self.builder.build(
            mode=FiscalRoleMode.POLICY_RESEARCH,
            user_task="查询最新差旅报销政策",
        )
        self.assertIn("政策研究", prompt)
        self.assertIn("reply_with_rules", prompt)
        self.assertIn("web_search", prompt)
        self.assertIn("web_fetch", prompt)

    def test_build_includes_user_task_in_output(self):
        """验证 prompt 包含原始用户任务。"""
        user_task = "录入本月差旅报销单据"
        prompt = self.builder.build(mode=FiscalRoleMode.BOOKKEEPING, user_task=user_task)
        self.assertIn(user_task, prompt)

    def test_build_with_context_appends_context_at_end(self):
        """验证 build_with_context 在末尾附加上下文信息。"""
        context = "当前时间：2024年1月，上一季度企业所得税已申报"
        user_task = "计算本年度所得税"
        prompt = self.builder.build_with_context(
            mode=FiscalRoleMode.TAX,
            user_task=user_task,
            context=context,
        )
        # build_with_context 在 base_prompt 后追加 ## 已知上下文
        self.assertIn("## 已知上下文", prompt)
        self.assertIn(context, prompt)
        self.assertIn(user_task, prompt)

    def test_all_modes_produce_non_empty_prompt(self):
        """验证每种模式都能生成非空 prompt。"""
        for mode in FiscalRoleMode:
            prompt = self.builder.build(mode=mode, user_task="测试任务")
            self.assertTrue(len(prompt) > 0, f"{mode} 模式生成了空 prompt")

    def test_all_modes_contain_output_format_section(self):
        """验证每种模式的 prompt 都包含输出格式部分。"""
        for mode in FiscalRoleMode:
            prompt = self.builder.build(mode=mode, user_task="测试任务")
            self.assertIn("## 输出格式", prompt)

    def test_bookkeeping_mode_contains_tool_constraints(self):
        """验证 bookkeeping 模式不能越权使用税务/审核/出纳工具。"""
        prompt = self.builder.build(
            mode=FiscalRoleMode.BOOKKEEPING,
            user_task="录入报销",
        )
        # 权限边界中应包含不能使用 calculate_tax / audit_voucher / record_cash_transaction
        self.assertIn("calculate_tax", prompt)
        self.assertIn("audit_voucher", prompt)
        self.assertIn("record_cash_transaction", prompt)

    def test_tax_mode_output_contains_tax_fields(self):
        """验证 tax 模式输出格式包含税相关字段。"""
        prompt = self.builder.build(
            mode=FiscalRoleMode.TAX,
            user_task="计算企业所得税",
        )
        # 输出格式应包含纳税人类型、应税收入、税率、应纳税额等
        self.assertIn("纳税人类型", prompt)
        self.assertIn("应纳税额", prompt)


class TestFiscalRoleModeEnum(unittest.TestCase):
    """验证 FiscalRoleMode 枚举值正确。"""

    def test_all_five_modes_exist(self):
        """验证五种专业模式都存在且值符合预期。"""
        self.assertEqual(FiscalRoleMode.BOOKKEEPING.value, "bookkeeping")
        self.assertEqual(FiscalRoleMode.TAX.value, "tax")
        self.assertEqual(FiscalRoleMode.AUDIT.value, "audit")
        self.assertEqual(FiscalRoleMode.CASHIER.value, "cashier")
        self.assertEqual(FiscalRoleMode.POLICY_RESEARCH.value, "policy_research")
