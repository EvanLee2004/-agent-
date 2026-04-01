"""旧 ledger 兼容投影服务。

该服务的职责是把新版 `JournalVoucher` 结构投影成旧版 `ledger` 风格字典，
用于兼容老接口、老脚本和迁移期展示。

关键点：
- 这是只读适配层，不负责写入旧表。
- 系统新的业务真相只保留在 `journal_voucher/journal_line`。
"""

from domain.models import JournalVoucher


class LegacyLedgerProjectionService:
    """旧账本兼容投影服务。"""

    def project_voucher(self, voucher: JournalVoucher) -> dict:
        """把单张凭证投影成旧 ledger 风格记录。"""
        return {
            "id": voucher.id,
            "datetime": self._build_legacy_datetime(voucher),
            "type": self._infer_legacy_entry_type(voucher),
            "amount": voucher.total_amount,
            "description": voucher.summary,
            "recorded_by": voucher.recorded_by,
            "status": voucher.status,
            "anomaly_flag": voucher.anomaly_flag,
            "anomaly_reason": voucher.anomaly_reason,
            "reviewed_by": voucher.reviewed_by,
            "created_at": voucher.created_at,
        }

    def project_vouchers(self, vouchers: list[JournalVoucher]) -> list[dict]:
        """批量投影凭证。"""
        return [self.project_voucher(voucher) for voucher in vouchers]

    @staticmethod
    def _build_legacy_datetime(voucher: JournalVoucher) -> str:
        """构造旧接口所需的 datetime 文本。

        旧接口按 `datetime LIKE 'YYYY-MM-DD%'` 做日期筛选，因此这里必须保留
        `voucher_date` 作为日期前缀；时间部分则沿用实际创建时间。
        """
        created_at = voucher.created_at.strip()
        if len(created_at) >= 19:
            time_part = created_at[11:19]
            return f"{voucher.voucher_date} {time_part}"
        return f"{voucher.voucher_date} 00:00:00"

    @staticmethod
    def _infer_legacy_entry_type(voucher: JournalVoucher) -> str:
        """根据凭证分录推断旧版收入/支出类型。"""
        income_subject_codes = {"5001"}
        for line in voucher.lines:
            if line.subject_code in income_subject_codes and line.credit_amount > 0:
                return "收入"
        return "支出"
