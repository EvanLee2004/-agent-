"""税务计算结果。"""

from dataclasses import dataclass, field

from tax.tax_type import TaxType
from tax.taxpayer_type import TaxpayerType


@dataclass(frozen=True)
class TaxComputationResult:
    """税务计算结果。"""

    tax_type: TaxType
    taxpayer_type: TaxpayerType
    taxable_base: float
    tax_rate: float
    payable_tax: float
    formula: str
    policy_basis: str
    notes: list[str] = field(default_factory=list)
