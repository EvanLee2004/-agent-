"""小公司本地测试账套生成器。"""

from dataclasses import dataclass, field

from accounting.accounting_service import AccountingService
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.voucher_draft import VoucherDraft
from audit.audit_service import AuditService
from audit.audit_request import AuditRequest
from audit.audit_target import AuditTarget
from audit.audit_voucher_command import AuditVoucherCommand


@dataclass(frozen=True)
class SampleLedgerSeedResult:
    """seed 结果。"""

    voucher_ids: list[int] = field(default_factory=list)
    invalid_cases: list[dict] = field(default_factory=list)


class SampleLedgerSeeder:
    """生成确定性小公司账套。

    测试数据不用真实企业数据，也不依赖外部数据集。这样可以保证每次测试都可重复，
    且科目、借贷方向、异常场景都符合当前项目的中国小企业会计科目口径。
    """

    def __init__(
        self,
        accounting_service: AccountingService,
        audit_service: AuditService,
    ):
        self._accounting_service = accounting_service
        self._audit_service = audit_service

    def seed(self) -> SampleLedgerSeedResult:
        """写入确定性样例凭证并执行一次全量审核。"""
        voucher_ids = [
            self._record(item)
            for item in self._build_valid_voucher_documents()
        ]
        self._audit_service.audit_voucher(
            AuditVoucherCommand(
                audit_request=AuditRequest(target=AuditTarget.ALL)
            )
        )
        return SampleLedgerSeedResult(
            voucher_ids=voucher_ids,
            invalid_cases=self._build_invalid_voucher_documents(),
        )

    def _record(self, document: dict) -> int:
        """写入单张样例凭证。"""
        return self._accounting_service.record_voucher(
            RecordVoucherCommand(voucher_draft=VoucherDraft.from_dict(document))
        )

    def _build_valid_voucher_documents(self) -> list[dict]:
        """构造可入账样例凭证。"""
        return [
            {
                "voucher_date": "2026-01-05",
                "summary": "销售商品收到银行存款",
                "source_text": "客户 A 支付销售货款 12000 元",
                "lines": [
                    {
                        "subject_code": "1002",
                        "subject_name": "银行存款",
                        "debit_amount": 12000,
                        "credit_amount": 0,
                        "description": "收到客户 A 货款",
                    },
                    {
                        "subject_code": "5001",
                        "subject_name": "主营业务收入",
                        "debit_amount": 0,
                        "credit_amount": 12000,
                        "description": "确认销售收入",
                    },
                ],
            },
            {
                "voucher_date": "2026-01-08",
                "summary": "采购商品形成应付账款",
                "source_text": "向供应商 B 采购商品 7000 元，尚未付款",
                "lines": [
                    {
                        "subject_code": "5401",
                        "subject_name": "主营业务成本",
                        "debit_amount": 7000,
                        "credit_amount": 0,
                        "description": "结转采购成本",
                    },
                    {
                        "subject_code": "2202",
                        "subject_name": "应付账款",
                        "debit_amount": 0,
                        "credit_amount": 7000,
                        "description": "形成供应商 B 应付款",
                    },
                ],
            },
            {
                "voucher_date": "2026-01-08",
                "summary": "采购商品形成应付账款",
                "source_text": "重复入账样例",
                "lines": [
                    {
                        "subject_code": "5401",
                        "subject_name": "主营业务成本",
                        "debit_amount": 7000,
                        "credit_amount": 0,
                        "description": "重复成本记录",
                    },
                    {
                        "subject_code": "2202",
                        "subject_name": "应付账款",
                        "debit_amount": 0,
                        "credit_amount": 7000,
                        "description": "重复应付款记录",
                    },
                ],
            },
            {
                "voucher_date": "2026-02-03",
                "summary": "大额设备采购预警",
                "source_text": "采购设备支付 68000 元",
                "lines": [
                    {
                        "subject_code": "6602",
                        "subject_name": "管理费用",
                        "debit_amount": 68000,
                        "credit_amount": 0,
                        "description": "设备相关支出",
                    },
                    {
                        "subject_code": "1002",
                        "subject_name": "银行存款",
                        "debit_amount": 0,
                        "credit_amount": 68000,
                        "description": "支付设备款",
                    },
                ],
            },
            {
                "voucher_date": "2026-02-10",
                "summary": "餐",
                "source_text": "摘要过短样例",
                "lines": [
                    {
                        "subject_code": "6602",
                        "subject_name": "管理费用",
                        "debit_amount": 300,
                        "credit_amount": 0,
                        "description": "",
                    },
                    {
                        "subject_code": "1001",
                        "subject_name": "库存现金",
                        "debit_amount": 0,
                        "credit_amount": 300,
                        "description": "现金报销",
                    },
                ],
            },
        ]

    def _build_invalid_voucher_documents(self) -> list[dict]:
        """构造不能入账但必须被测试覆盖的负例。"""
        return [
            {
                "voucher_date": "2026-03-01",
                "summary": "借贷不平负例",
                "source_text": "该凭证仅用于验证校验失败",
                "lines": [
                    {
                        "subject_code": "6601",
                        "subject_name": "销售费用",
                        "debit_amount": 100,
                        "credit_amount": 0,
                        "description": "广告费",
                    },
                    {
                        "subject_code": "1002",
                        "subject_name": "银行存款",
                        "debit_amount": 0,
                        "credit_amount": 90,
                        "description": "付款金额不一致",
                    },
                ],
            }
        ]
