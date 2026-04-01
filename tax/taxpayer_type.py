"""纳税主体枚举。"""

from enum import Enum


class TaxpayerType(str, Enum):
    """当前支持的纳税主体类型。"""

    SMALL_SCALE_VAT = "small_scale_vat_taxpayer"
    SMALL_LOW_PROFIT_ENTERPRISE = "small_low_profit_enterprise"
