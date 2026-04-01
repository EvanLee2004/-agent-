"""税务领域模型。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


TAX_TYPE_ALIASES = {
    "vat": "vat",
    "增值税": "vat",
    "corporate_income_tax": "corporate_income_tax",
    "企业所得税": "corporate_income_tax",
}

TAXPAYER_TYPE_ALIASES = {
    "small_scale_vat_taxpayer": "small_scale_vat_taxpayer",
    "small_scale_vat_taxaxpayer": "small_scale_vat_taxpayer",
    "小规模纳税人": "small_scale_vat_taxpayer",
    "小规模增值税纳税人": "small_scale_vat_taxpayer",
    "small_low_profit_enterprise": "small_low_profit_enterprise",
    "小型微利企业": "small_low_profit_enterprise",
}


class TaxType(str, Enum):
    """当前支持的税种类型。"""

    VAT = "vat"
    CORPORATE_INCOME_TAX = "corporate_income_tax"


class TaxpayerType(str, Enum):
    """当前支持的纳税主体类型。"""

    SMALL_SCALE_VAT = "small_scale_vat_taxpayer"
    SMALL_LOW_PROFIT_ENTERPRISE = "small_low_profit_enterprise"


@dataclass
class TaxRequest:
    """税务计算请求。"""

    tax_type: TaxType
    taxpayer_type: TaxpayerType
    amount: float
    includes_tax: bool = False
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "TaxRequest":
        """从字典创建税务请求并校验。

        这里在领域层加入一层非常轻量的归一化，目的不是放松约束，
        而是屏蔽两类在真实模型联调里已经出现过的噪声：
        1. 中文同义表达，例如“增值税”“小规模纳税人”
        2. 少量可预见的 OpenAI-compatible 工具参数拼写漂移

        归一化之后仍然会落到严格的枚举校验，因此不会把任意字符串都吞掉。
        """
        request = cls(
            tax_type=TaxType(cls._normalize_tax_type(data["tax_type"])),
            taxpayer_type=TaxpayerType(
                cls._normalize_taxpayer_type(data["taxpayer_type"])
            ),
            amount=float(data["amount"]),
            includes_tax=bool(data.get("includes_tax", False)),
            description=str(data.get("description", "")).strip() or None,
        )
        request.validate()
        return request

    def validate(self) -> None:
        """校验税务请求合法性。"""
        if self.amount <= 0:
            raise ValueError("税务计算金额必须为正数")

    @staticmethod
    def _normalize_tax_type(value: object) -> str:
        """把税种输入归一化为系统枚举值。"""
        raw_value = str(value).strip()
        return TAX_TYPE_ALIASES.get(raw_value, raw_value)

    @staticmethod
    def _normalize_taxpayer_type(value: object) -> str:
        """把纳税主体输入归一化为系统枚举值。"""
        raw_value = str(value).strip()
        return TAXPAYER_TYPE_ALIASES.get(raw_value, raw_value)


@dataclass
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
