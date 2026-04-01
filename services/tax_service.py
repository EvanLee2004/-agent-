"""税务应用服务。

第一版只实现全国统一、规则稳定且容易核验的基础税计算：
1. 小规模纳税人增值税
2. 小型微利企业企业所得税

这里采用“LLM 负责提取参数，Service 负责确定性计算”的模式，
原因是税额计算属于高确定性任务，不适合完全交给模型自由发挥。
"""

from domain.tax import TaxComputationResult, TaxRequest, TaxType, TaxpayerType


SMALL_SCALE_VAT_RATE = 0.01
SMALL_LOW_PROFIT_EFFECTIVE_CIT_RATE = 0.05
PREFERENTIAL_POLICY_DEADLINE = "2027-12-31"


class TaxService:
    """税务应用服务。"""

    def calculate(self, request: TaxRequest) -> TaxComputationResult:
        """按请求计算税额。"""
        request.validate()

        if (
            request.tax_type == TaxType.VAT
            and request.taxpayer_type == TaxpayerType.SMALL_SCALE_VAT
        ):
            return self._calculate_small_scale_vat(request)

        if (
            request.tax_type == TaxType.CORPORATE_INCOME_TAX
            and request.taxpayer_type == TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE
        ):
            return self._calculate_small_low_profit_cit(request)

        raise ValueError("当前版本仅支持小规模纳税人增值税和小型微利企业企业所得税计算")

    def _calculate_small_scale_vat(self, request: TaxRequest) -> TaxComputationResult:
        """计算小规模纳税人增值税。"""
        if request.includes_tax:
            taxable_base = round(request.amount / (1 + SMALL_SCALE_VAT_RATE), 2)
            payable_tax = round(request.amount - taxable_base, 2)
            formula = (
                f"含税销售额 {request.amount:.2f} / 1.01 = 不含税销售额 {taxable_base:.2f}，"
                f"税额 = {request.amount:.2f} - {taxable_base:.2f}"
            )
        else:
            taxable_base = round(request.amount, 2)
            payable_tax = round(taxable_base * SMALL_SCALE_VAT_RATE, 2)
            formula = (
                f"不含税销售额 {taxable_base:.2f} x 1% = 应纳增值税 {payable_tax:.2f}"
            )

        return TaxComputationResult(
            tax_type=request.tax_type,
            taxpayer_type=request.taxpayer_type,
            taxable_base=taxable_base,
            tax_rate=SMALL_SCALE_VAT_RATE,
            payable_tax=payable_tax,
            formula=formula,
            policy_basis=(
                "国家税务总局口径：小规模纳税人减按1%征收率征收增值税，"
                f"优惠政策执行至 {PREFERENTIAL_POLICY_DEADLINE}"
            ),
            notes=[
                "当前结果仅覆盖增值税本身，不自动展开地方附加税费明细。",
                "如涉及免税、差额征税或特定行业政策，应另行人工复核。",
            ],
        )

    def _calculate_small_low_profit_cit(
        self,
        request: TaxRequest,
    ) -> TaxComputationResult:
        """计算小型微利企业企业所得税。"""
        taxable_base = round(request.amount, 2)
        payable_tax = round(
            taxable_base * SMALL_LOW_PROFIT_EFFECTIVE_CIT_RATE,
            2,
        )
        formula = (
            f"应纳税所得额 {taxable_base:.2f} x 25% x 20% = 应纳企业所得税 {payable_tax:.2f}"
        )
        return TaxComputationResult(
            tax_type=request.tax_type,
            taxpayer_type=request.taxpayer_type,
            taxable_base=taxable_base,
            tax_rate=SMALL_LOW_PROFIT_EFFECTIVE_CIT_RATE,
            payable_tax=payable_tax,
            formula=formula,
            policy_basis=(
                "国家税务总局口径：小型微利企业减按25%计入应纳税所得额，"
                f"按20%税率缴纳企业所得税，优惠政策执行至 {PREFERENTIAL_POLICY_DEADLINE}"
            ),
            notes=[
                "当前计算把输入金额直接视为应纳税所得额。",
                "是否满足从业人数、资产总额等资格条件，需要结合企业实际情况人工确认。",
            ],
        )
