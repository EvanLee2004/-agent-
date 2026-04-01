"""税种枚举。"""

from enum import Enum


class TaxType(str, Enum):
    """当前支持的税种类型。"""

    VAT = "vat"
    CORPORATE_INCOME_TAX = "corporate_income_tax"
