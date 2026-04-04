"""税务服务测试。"""

import unittest

from tax.calculate_tax_command import CalculateTaxCommand
from tax.tax_computation_result import TaxComputationResult
from tax.tax_error import TaxError
from tax.tax_request import TaxRequest
from tax.tax_service import TaxService
from tax.tax_type import TaxType
from tax.taxpayer_type import TaxpayerType


class TestTaxService(unittest.TestCase):
    """税务服务测试。"""

    def setUp(self):
        """设置测试 fixtures。"""
        self._service = TaxService()

    # ===== 小规模纳税人增值税测试 =====

    def test_small_scale_vat_excluded_tax(self):
        """测试不含税销售额增值税计算。"""
        request = TaxRequest(
            tax_type=TaxType.VAT,
            taxpayer_type=TaxpayerType.SMALL_SCALE_VAT,
            amount=100000.0,
            includes_tax=False,
        )
        result = self._service.calculate_tax(
            CalculateTaxCommand(tax_request=request)
        )
        self.assertEqual(result.payable_tax, 1000.0)
        self.assertEqual(result.taxable_base, 100000.0)
        self.assertEqual(result.tax_rate, 0.01)

    def test_small_scale_vat_included_tax(self):
        """测试含税销售额增值税计算。"""
        request = TaxRequest(
            tax_type=TaxType.VAT,
            taxpayer_type=TaxpayerType.SMALL_SCALE_VAT,
            amount=101000.0,
            includes_tax=True,
        )
        result = self._service.calculate_tax(
            CalculateTaxCommand(tax_request=request)
        )
        self.assertEqual(result.taxable_base, 100000.0)
        self.assertEqual(result.payable_tax, 1000.0)

    # ===== 小型微利企业企业所得税测试 =====

    def test_cit_without_cost(self):
        """测试无成本的企业所得税计算（向后兼容）。"""
        request = TaxRequest(
            tax_type=TaxType.CORPORATE_INCOME_TAX,
            taxpayer_type=TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE,
            amount=1000000.0,
        )
        result = self._service.calculate_tax(
            CalculateTaxCommand(tax_request=request)
        )
        # 100万 x 5% = 5万
        self.assertEqual(result.payable_tax, 50000.0)
        self.assertEqual(result.taxable_base, 1000000.0)

    def test_cit_with_cost(self):
        """测试有成本的企业所得税计算。"""
        request = TaxRequest(
            tax_type=TaxType.CORPORATE_INCOME_TAX,
            taxpayer_type=TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE,
            amount=1000000.0,
            cost=600000.0,
        )
        result = self._service.calculate_tax(
            CalculateTaxCommand(tax_request=request)
        )
        # (100万 - 60万) x 5% = 2万
        self.assertEqual(result.payable_tax, 20000.0)
        self.assertEqual(result.taxable_base, 400000.0)
        self.assertIn("收入", result.formula)
        self.assertIn("成本费用", result.formula)

    def test_cit_zero_cost(self):
        """测试成本为零的情况。"""
        request = TaxRequest(
            tax_type=TaxType.CORPORATE_INCOME_TAX,
            taxpayer_type=TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE,
            amount=1000000.0,
            cost=0.0,
        )
        result = self._service.calculate_tax(
            CalculateTaxCommand(tax_request=request)
        )
        self.assertEqual(result.payable_tax, 50000.0)
        self.assertEqual(result.taxable_base, 1000000.0)
        # 成本为0时，公式不应包含成本费用
        self.assertNotIn("成本费用", result.formula)

    def test_cit_cost_equals_revenue(self):
        """测试成本等于收入的情况（亏损）。"""
        request = TaxRequest(
            tax_type=TaxType.CORPORATE_INCOME_TAX,
            taxpayer_type=TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE,
            amount=1000000.0,
            cost=1000000.0,
        )
        result = self._service.calculate_tax(
            CalculateTaxCommand(tax_request=request)
        )
        # (100万 - 100万) x 5% = 0
        self.assertEqual(result.payable_tax, 0.0)
        self.assertEqual(result.taxable_base, 0.0)

    # ===== TaxRequest 验证测试 =====

    def test_negative_amount_rejected(self):
        """测试负数金额被拒绝。"""
        with self.assertRaises(TaxError) as ctx:
            TaxRequest(
                tax_type=TaxType.VAT,
                taxpayer_type=TaxpayerType.SMALL_SCALE_VAT,
                amount=-1000.0,
            ).validate()
        self.assertIn("正数", str(ctx.exception))

    def test_negative_cost_rejected(self):
        """测试负数成本被拒绝。"""
        with self.assertRaises(TaxError) as ctx:
            TaxRequest(
                tax_type=TaxType.CORPORATE_INCOME_TAX,
                taxpayer_type=TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE,
                amount=1000000.0,
                cost=-100.0,
            ).validate()
        self.assertIn("成本不能为负数", str(ctx.exception))

    def test_cost_greater_than_amount_rejected(self):
        """测试成本大于收入被拒绝。"""
        with self.assertRaises(TaxError) as ctx:
            TaxRequest(
                tax_type=TaxType.CORPORATE_INCOME_TAX,
                taxpayer_type=TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE,
                amount=1000000.0,
                cost=1500000.0,
            ).validate()
        self.assertIn("成本不能大于收入", str(ctx.exception))

    # ===== from_dict 测试 =====

    def test_from_dict_with_cost(self):
        """测试从字典构造带成本的请求。"""
        data = {
            "tax_type": "corporate_income_tax",
            "taxpayer_type": "small_low_profit_enterprise",
            "amount": 1000000.0,
            "cost": 600000.0,
        }
        request = TaxRequest.from_dict(data)
        self.assertEqual(request.cost, 600000.0)
        self.assertEqual(request.amount, 1000000.0)

    def test_from_dict_without_cost(self):
        """测试从字典构造不带成本的请求（向后兼容）。"""
        data = {
            "tax_type": "vat",
            "taxpayer_type": "small_scale_vat_taxpayer",
            "amount": 100000.0,
        }
        request = TaxRequest.from_dict(data)
        self.assertEqual(request.cost, 0.0)

    def test_from_dict_typo_taxpayer_type(self):
        """测试带拼写错误的纳税人类型别名（已修复）。"""
        # 旧的拼写错误 "small_scale_vat_taxaxpayer" 应该不再存在
        data = {
            "tax_type": "vat",
            "taxpayer_type": "small_scale_vat_taxpayer",
            "amount": 100000.0,
        }
        request = TaxRequest.from_dict(data)
        self.assertEqual(request.taxpayer_type, TaxpayerType.SMALL_SCALE_VAT)


class TestTaxServiceIntegration(unittest.TestCase):
    """税务服务集成测试。"""

    def setUp(self):
        """设置测试 fixtures。"""
        self._service = TaxService()

    def test_full_cit_calculation_flow(self):
        """测试完整的企业所得税计算流程（收入100万，成本60万）。"""
        # 场景：企业收入100万，成本费用60万
        request = TaxRequest(
            tax_type=TaxType.CORPORATE_INCOME_TAX,
            taxpayer_type=TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE,
            amount=1000000.0,
            cost=600000.0,
            description="主营业务收入减去成本费用",
        )
        result = self._service.calculate_tax(
            CalculateTaxCommand(tax_request=request)
        )

        # 验证计算结果
        # 应纳税所得额 = 100万 - 60万 = 40万
        # 应纳税额 = 40万 x 5% = 2万
        self.assertEqual(result.taxable_base, 400000.0)
        self.assertEqual(result.payable_tax, 20000.0)

        # 验证公式包含正确信息
        self.assertIn("1000000.00", result.formula)
        self.assertIn("600000.00", result.formula)
        self.assertIn("400000.00", result.formula)
        self.assertIn("20000.00", result.formula)

        # 验证政策依据存在
        self.assertIn("小型微利企业", result.policy_basis)
        self.assertIn("25%", result.policy_basis)
        self.assertIn("20%", result.policy_basis)


if __name__ == "__main__":
    unittest.main()
