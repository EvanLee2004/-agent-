"""审核应用服务。

第一版审核能力定位为“凭证规则审核”，而不是完整审计专家系统。
它关注的是结构化账务数据里最容易解释、最容易复核的问题：
- 借贷是否平衡
- 金额是否异常
- 是否存在明显重复凭证
- 摘要和分录是否过于空泛
"""

from domain.models import AuditFlag, AuditRequest, AuditResult, AuditTarget, JournalVoucher
from services.voucher_service import VoucherService


SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


class AuditService:
    """审核应用服务。"""

    def __init__(self, voucher_service: VoucherService):
        self._voucher_service = voucher_service

    def audit(self, request: AuditRequest) -> AuditResult:
        """执行凭证审核。"""
        request.validate()

        target_vouchers = self._select_target_vouchers(request)
        if not target_vouchers:
            raise ValueError("未找到可审核的凭证")

        all_vouchers = self._voucher_service.list_vouchers(limit=500)
        flags: list[AuditFlag] = []

        for voucher in target_vouchers:
            flags.extend(self._audit_single_voucher(voucher, all_vouchers))

        risk_level = self._resolve_risk_level(flags)
        audited_ids = [voucher.id for voucher in target_vouchers]
        summary = f"已审核 {len(target_vouchers)} 张凭证，风险等级：{risk_level}"
        suggestion = "建议优先复核高风险标记，再确认摘要和金额是否符合实际业务。"
        return AuditResult(
            audited_voucher_ids=audited_ids,
            risk_level=risk_level,
            summary=summary,
            flags=flags,
            suggestion=suggestion,
        )

    def format_result(self, result: AuditResult) -> str:
        """格式化审核结果。"""
        lines = [
            result.summary,
            f"- 凭证ID: {', '.join(str(item) for item in result.audited_voucher_ids)}",
        ]
        if not result.flags:
            lines.append("- 未发现明显异常")
        else:
            for flag in result.flags:
                lines.append(
                    f"- [{flag.severity.upper()}] {flag.code}: {flag.message}"
                )
        if result.suggestion:
            lines.append(f"- 建议: {result.suggestion}")
        return "\n".join(lines)

    def _select_target_vouchers(self, request: AuditRequest) -> list[JournalVoucher]:
        """根据审核请求选择目标凭证。"""
        if request.target == AuditTarget.ALL:
            return self._voucher_service.list_vouchers(limit=100)

        if request.target == AuditTarget.VOUCHER_ID:
            voucher = self._voucher_service.get_voucher_by_id(request.voucher_id or 0)
            return [voucher] if voucher else []

        latest_voucher = self._voucher_service.get_latest_voucher()
        return [latest_voucher] if latest_voucher else []

    def _audit_single_voucher(
        self,
        voucher: JournalVoucher,
        all_vouchers: list[JournalVoucher],
    ) -> list[AuditFlag]:
        """审核单张凭证。"""
        flags: list[AuditFlag] = []
        total_debit = round(sum(line.debit_amount for line in voucher.lines), 2)
        total_credit = round(sum(line.credit_amount for line in voucher.lines), 2)

        if abs(total_debit - total_credit) > 0.01:
            flags.append(
                AuditFlag(
                    code="UNBALANCED",
                    severity="high",
                    message=(
                        f"凭证 {voucher.id} 借贷不平衡：借方 {total_debit:.2f}，贷方 {total_credit:.2f}"
                    ),
                )
            )

        if voucher.total_amount > 50000:
            flags.append(
                AuditFlag(
                    code="LARGE_AMOUNT",
                    severity="high",
                    message=f"凭证 {voucher.id} 金额 {voucher.total_amount:.2f}元，超过项目预设审核阈值",
                )
            )
        elif 0 < voucher.total_amount < 10:
            flags.append(
                AuditFlag(
                    code="SMALL_AMOUNT",
                    severity="low",
                    message=f"凭证 {voucher.id} 金额 {voucher.total_amount:.2f}元，金额过小，建议复核",
                )
            )

        if len(voucher.summary.strip()) < 4:
            flags.append(
                AuditFlag(
                    code="WEAK_SUMMARY",
                    severity="medium",
                    message=f"凭证 {voucher.id} 摘要过短，难以支持后续审阅与追踪",
                )
            )

        if self._has_duplicate_voucher(voucher, all_vouchers):
            flags.append(
                AuditFlag(
                    code="POSSIBLE_DUPLICATE",
                    severity="medium",
                    message=f"凭证 {voucher.id} 与已有凭证在日期、摘要和金额上高度重复",
                )
            )

        for line in voucher.lines:
            if not line.description.strip():
                flags.append(
                    AuditFlag(
                        code="MISSING_LINE_DESCRIPTION",
                        severity="low",
                        message=f"凭证 {voucher.id} 存在未填写分录说明的行",
                    )
                )
                break

        return flags

    @staticmethod
    def _has_duplicate_voucher(
        current_voucher: JournalVoucher,
        all_vouchers: list[JournalVoucher],
    ) -> bool:
        """检查是否存在高度重复凭证。"""
        for voucher in all_vouchers:
            if voucher.id == current_voucher.id:
                continue
            if (
                voucher.voucher_date == current_voucher.voucher_date
                and voucher.summary == current_voucher.summary
                and abs(voucher.total_amount - current_voucher.total_amount) < 0.01
            ):
                return True
        return False

    @staticmethod
    def _resolve_risk_level(flags: list[AuditFlag]) -> str:
        """根据全部标记推导最终风险等级。"""
        highest = 0
        for flag in flags:
            highest = max(highest, SEVERITY_ORDER.get(flag.severity, 0))

        if highest >= SEVERITY_ORDER["high"]:
            return "high"
        if highest >= SEVERITY_ORDER["medium"]:
            return "medium"
        return "low"
