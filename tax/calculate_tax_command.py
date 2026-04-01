"""税务计算命令。"""

from dataclasses import dataclass

from tax.tax_request import TaxRequest


@dataclass(frozen=True)
class CalculateTaxCommand:
    """税务计算命令。"""

    tax_request: TaxRequest
