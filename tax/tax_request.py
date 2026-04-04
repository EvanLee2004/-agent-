"""税务计算请求。"""

from dataclasses import dataclass
from typing import Optional

from tax.tax_error import TaxError
from tax.tax_type import TaxType
from tax.taxpayer_type import TaxpayerType


TAX_TYPE_ALIASES = {
    "vat": "vat",
    "增值税": "vat",
    "corporate_income_tax": "corporate_income_tax",
    "企业所得税": "corporate_income_tax",
}

TAXPAYER_TYPE_ALIASES = {
    "small_scale_vat_taxpayer": "small_scale_vat_taxpayer",
    "小规模纳税人": "small_scale_vat_taxpayer",
    "小规模增值税纳税人": "small_scale_vat_taxpayer",
    "small_low_profit_enterprise": "small_low_profit_enterprise",
    "小型微利企业": "small_low_profit_enterprise",
}


@dataclass(frozen=True)
class TaxRequest:
    """税务计算请求。"""

    tax_type: TaxType
    taxpayer_type: TaxpayerType
    amount: float
    includes_tax: bool = False
    cost: float = 0.0
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "TaxRequest":
        """从字典构造税务请求。"""
        request = cls(
            tax_type=TaxType(cls._normalize_tax_type(data["tax_type"])),
            taxpayer_type=TaxpayerType(cls._normalize_taxpayer_type(data["taxpayer_type"])),
            amount=float(data["amount"]),
            includes_tax=bool(data.get("includes_tax", False)),
            cost=float(data.get("cost", 0.0)),
            description=str(data.get("description", "")).strip() or None,
        )
        request.validate()
        return request

    def validate(self) -> None:
        """校验税务请求。"""
        if self.amount <= 0:
            raise TaxError("税务计算金额必须为正数")
        if self.cost < 0:
            raise TaxError("成本不能为负数")
        if self.cost > self.amount:
            raise TaxError("成本不能大于收入")

    @staticmethod
    def _normalize_tax_type(value: object) -> str:
        """归一化税种。"""
        raw_value = str(value).strip()
        return TAX_TYPE_ALIASES.get(raw_value, raw_value)

    @staticmethod
    def _normalize_taxpayer_type(value: object) -> str:
        """归一化纳税主体。"""
        raw_value = str(value).strip()
        return TAXPAYER_TYPE_ALIASES.get(raw_value, raw_value)
