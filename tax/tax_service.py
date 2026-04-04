"""税务服务。"""

from tax.calculate_tax_command import CalculateTaxCommand
from tax.tax_computation_result import TaxComputationResult
from tax.tax_error import TaxError
from tax.tax_request import TaxRequest
from tax.tax_type import TaxType
from tax.taxpayer_type import TaxpayerType


SMALL_SCALE_VAT_RATE = 0.01
SMALL_LOW_PROFIT_EFFECTIVE_CIT_RATE = 0.05
PREFERENTIAL_POLICY_DEADLINE = "2027-12-31"


def _build_small_scale_vat_policy_basis() -> str:
    """构造小规模纳税人增值税政策依据。"""
    return (
        "国家税务总局口径：小规模纳税人减按1%征收率征收增值税，"
        f"优惠政策执行至 {PREFERENTIAL_POLICY_DEADLINE}"
    )


def _build_small_low_profit_cit_policy_basis() -> str:
    """构造小型微利企业所得税政策依据。"""
    return (
        "国家税务总局口径：小型微利企业减按25%计入应纳税所得额，"
        f"按20%税率缴纳企业所得税，优惠政策执行至 {PREFERENTIAL_POLICY_DEADLINE}"
    )


class TaxService:
    """税务服务。"""

    def calculate_tax(self, command: CalculateTaxCommand) -> TaxComputationResult:
        """计算税额。

        Args:
            command: 税务计算命令。

        Returns:
            税务计算结果。

        Raises:
            TaxError: 当前税种与纳税主体组合不支持时抛出。
        """
        request = command.tax_request
        request.validate()
        if self._is_small_scale_vat_request(request):
            return self._calculate_small_scale_vat(request)
        if self._is_small_low_profit_cit_request(request):
            return self._calculate_small_low_profit_cit(request)
        raise TaxError("当前版本仅支持小规模纳税人增值税和小型微利企业企业所得税计算")

    def _is_small_scale_vat_request(self, request: TaxRequest) -> bool:
        """判断是否为小规模纳税人增值税请求。"""
        return (
            request.tax_type == TaxType.VAT
            and request.taxpayer_type == TaxpayerType.SMALL_SCALE_VAT
        )

    def _is_small_low_profit_cit_request(self, request: TaxRequest) -> bool:
        """判断是否为小型微利企业所得税请求。"""
        return (
            request.tax_type == TaxType.CORPORATE_INCOME_TAX
            and request.taxpayer_type == TaxpayerType.SMALL_LOW_PROFIT_ENTERPRISE
        )

    def _calculate_small_scale_vat(self, request: TaxRequest) -> TaxComputationResult:
        """计算小规模纳税人增值税。"""
        taxable_base, payable_tax, formula = self._resolve_small_scale_vat_values(request)
        return TaxComputationResult(
            tax_type=request.tax_type,
            taxpayer_type=request.taxpayer_type,
            taxable_base=taxable_base,
            tax_rate=SMALL_SCALE_VAT_RATE,
            payable_tax=payable_tax,
            formula=formula,
            policy_basis=_build_small_scale_vat_policy_basis(),
            notes=[
                "当前结果仅覆盖增值税本身，不自动展开地方附加税费明细。",
                "如涉及免税、差额征税或特定行业政策，应另行人工复核。",
            ],
        )

    def _resolve_small_scale_vat_values(self, request: TaxRequest) -> tuple[float, float, str]:
        """计算小规模纳税人增值税的应税基础与公式。"""
        if request.includes_tax:
            return self._calculate_tax_included_vat(request.amount)
        return self._calculate_tax_excluded_vat(request.amount)

    def _calculate_tax_included_vat(self, amount: float) -> tuple[float, float, str]:
        """计算含税销售额下的增值税。"""
        taxable_base = round(amount / (1 + SMALL_SCALE_VAT_RATE), 2)
        payable_tax = round(amount - taxable_base, 2)
        formula = (
            f"含税销售额 {amount:.2f} / 1.01 = 不含税销售额 {taxable_base:.2f}，"
            f"税额 = {amount:.2f} - {taxable_base:.2f}"
        )
        return taxable_base, payable_tax, formula

    def _calculate_tax_excluded_vat(self, amount: float) -> tuple[float, float, str]:
        """计算不含税销售额下的增值税。"""
        taxable_base = round(amount, 2)
        payable_tax = round(taxable_base * SMALL_SCALE_VAT_RATE, 2)
        formula = f"不含税销售额 {taxable_base:.2f} x 1% = 应纳增值税 {payable_tax:.2f}"
        return taxable_base, payable_tax, formula

    def _calculate_small_low_profit_cit(self, request: TaxRequest) -> TaxComputationResult:
        """计算小型微利企业企业所得税。"""
        taxable_base = round(request.amount - request.cost, 2)
        payable_tax = round(taxable_base * SMALL_LOW_PROFIT_EFFECTIVE_CIT_RATE, 2)
        if request.cost > 0:
            formula = (
                f"收入 {request.amount:.2f} - 成本费用 {request.cost:.2f} = "
                f"应纳税所得额 {taxable_base:.2f} x 25% x 20% = 应纳企业所得税 {payable_tax:.2f}"
            )
        else:
            formula = f"应纳税所得额 {taxable_base:.2f} x 25% x 20% = 应纳企业所得税 {payable_tax:.2f}"
        return TaxComputationResult(
            tax_type=request.tax_type,
            taxpayer_type=request.taxpayer_type,
            taxable_base=taxable_base,
            tax_rate=SMALL_LOW_PROFIT_EFFECTIVE_CIT_RATE,
            payable_tax=payable_tax,
            formula=formula,
            policy_basis=_build_small_low_profit_cit_policy_basis(),
            notes=[
                "当前结果已根据收入和成本费用计算应纳税所得额。",
                "是否满足从业人数、资产总额等资格条件，需要结合企业实际情况人工确认。",
            ],
        )
