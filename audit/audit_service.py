"""审核服务。"""

from accounting.journal_repository import JournalRepository
from accounting.query_vouchers_query import QueryVouchersQuery
from audit.audit_error import AuditError
from audit.audit_flag import AuditFlag
from audit.audit_request import AuditRequest
from audit.audit_result import AuditResult
from audit.audit_target import AuditTarget
from audit.audit_voucher_command import AuditVoucherCommand
from configuration.defaults import HIGH_AMOUNT_THRESHOLD, LOW_AMOUNT_THRESHOLD


SEVERITY_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

DUPLICATE_TOLERANCE = 0.01


def _build_unbalanced_flag(
    voucher, total_debit: float, total_credit: float
) -> AuditFlag:
    """构造借贷不平标记。"""
    return AuditFlag(
        code="UNBALANCED",
        severity="high",
        voucher_id=voucher.voucher_id,
        message=f"凭证 {voucher.voucher_id} 借贷不平衡：借方 {total_debit:.2f}，贷方 {total_credit:.2f}",
    )


def _build_large_amount_flag(voucher, total_amount: float) -> AuditFlag:
    """构造大额标记。"""
    return AuditFlag(
        code="LARGE_AMOUNT",
        severity="high",
        voucher_id=voucher.voucher_id,
        message=f"凭证 {voucher.voucher_id} 金额 {total_amount:.2f}元，超过项目预设审核阈值",
    )


def _build_small_amount_flag(voucher, total_amount: float) -> AuditFlag:
    """构造小额标记。"""
    return AuditFlag(
        code="SMALL_AMOUNT",
        severity="low",
        voucher_id=voucher.voucher_id,
        message=f"凭证 {voucher.voucher_id} 金额 {total_amount:.2f}元，金额过小，建议复核",
    )


def _build_weak_summary_flag(voucher) -> AuditFlag:
    """构造摘要过短标记。"""
    return AuditFlag(
        code="WEAK_SUMMARY",
        severity="medium",
        voucher_id=voucher.voucher_id,
        message=f"凭证 {voucher.voucher_id} 摘要过短，难以支持后续审阅与追踪",
    )


def _build_duplicate_flag(voucher) -> AuditFlag:
    """构造疑似重复标记。"""
    return AuditFlag(
        code="POSSIBLE_DUPLICATE",
        severity="medium",
        voucher_id=voucher.voucher_id,
        message=f"凭证 {voucher.voucher_id} 与已有凭证在日期、摘要和金额上高度重复",
    )


def _build_missing_line_description_flag(voucher) -> AuditFlag:
    """构造缺少分录说明标记。"""
    return AuditFlag(
        code="MISSING_LINE_DESCRIPTION",
        severity="low",
        voucher_id=voucher.voucher_id,
        message=f"凭证 {voucher.voucher_id} 存在未填写分录说明的行",
    )


class AuditService:
    """审核服务。"""

    def __init__(self, journal_repository: JournalRepository):
        self._journal_repository = journal_repository

    def audit_voucher(self, command: AuditVoucherCommand) -> AuditResult:
        """执行凭证审核。"""
        request = command.audit_request
        request.validate()
        target_vouchers = self._select_target_vouchers(request)
        if not target_vouchers:
            raise AuditError("未找到可审核的凭证")

        if request.target == AuditTarget.ALL:
            all_vouchers = target_vouchers
        else:
            all_vouchers = self._journal_repository.list_vouchers(
                QueryVouchersQuery(limit=500)
            )
        flags = self._collect_audit_flags(target_vouchers, all_vouchers)

        risk_level = self._resolve_risk_level(flags)
        self._update_voucher_status(target_vouchers, flags)
        return AuditResult(
            audited_voucher_ids=[voucher.voucher_id for voucher in target_vouchers],
            risk_level=risk_level,
            summary=f"已审核 {len(target_vouchers)} 张凭证，风险等级：{risk_level}",
            flags=flags,
            suggestion="建议优先复核高风险标记，再确认摘要和金额是否符合实际业务。",
        )

    def _collect_audit_flags(
        self, target_vouchers: list, all_vouchers: list
    ) -> list[AuditFlag]:
        """汇总多张凭证的审核标记。"""
        flags = []
        for voucher in target_vouchers:
            flags.extend(self._audit_single_voucher(voucher, all_vouchers))
        return flags

    def _select_target_vouchers(self, request: AuditRequest) -> list:
        """选择审核目标凭证。"""
        if request.target == AuditTarget.ALL:
            return self._journal_repository.list_vouchers(QueryVouchersQuery(limit=100))
        if request.target == AuditTarget.VOUCHER_ID:
            voucher = self._journal_repository.get_voucher_by_id(
                request.voucher_id or 0
            )
            if voucher is None:
                return []
            return [voucher]
        latest_voucher = self._journal_repository.get_latest_voucher()
        if latest_voucher is None:
            return []
        return [latest_voucher]

    def _audit_single_voucher(self, voucher, all_vouchers: list) -> list[AuditFlag]:
        """审核单张凭证。"""
        flags = []
        flags.extend(self._build_balance_flags(voucher))
        flags.extend(self._build_amount_flags(voucher))
        flags.extend(self._build_summary_flags(voucher))
        flags.extend(self._build_duplicate_flags(voucher, all_vouchers))
        flags.extend(self._build_line_description_flags(voucher))
        return flags

    def _build_balance_flags(self, voucher) -> list[AuditFlag]:
        """构造借贷平衡相关标记。"""
        total_debit = round(sum(line.debit_amount for line in voucher.lines), 2)
        total_credit = round(sum(line.credit_amount for line in voucher.lines), 2)
        if abs(total_debit - total_credit) <= DUPLICATE_TOLERANCE:
            return []
        return [_build_unbalanced_flag(voucher, total_debit, total_credit)]

    def _build_amount_flags(self, voucher) -> list[AuditFlag]:
        """构造金额异常相关标记。"""
        total_amount = voucher.get_total_amount()
        if total_amount > HIGH_AMOUNT_THRESHOLD:
            return [_build_large_amount_flag(voucher, total_amount)]
        if 0 < total_amount < LOW_AMOUNT_THRESHOLD:
            return [_build_small_amount_flag(voucher, total_amount)]
        return []

    def _build_summary_flags(self, voucher) -> list[AuditFlag]:
        """构造摘要质量相关标记。"""
        if len(voucher.summary.strip()) < 4:
            return [_build_weak_summary_flag(voucher)]
        return []

    def _build_duplicate_flags(self, voucher, all_vouchers: list) -> list[AuditFlag]:
        """构造疑似重复入账标记。"""
        if self._has_duplicate_voucher(voucher, all_vouchers):
            return [_build_duplicate_flag(voucher)]
        return []

    def _build_line_description_flags(self, voucher) -> list[AuditFlag]:
        """构造分录说明缺失标记。"""
        if self._has_blank_line_description(voucher):
            return [_build_missing_line_description_flag(voucher)]
        return []

    def _has_duplicate_voucher(self, current_voucher, all_vouchers: list) -> bool:
        """判断是否重复凭证。

        判断逻辑：遍历所有凭证，对每个非自身的凭证，检查：
        - 日期相同
        - 摘要相同
        - 金额相同（误差小于 DUPLICATE_TOLERANCE）

        使用 == 而不是 != 来跳过自身：这是因为 all_vouchers 中可能包含
        current_voucher 自身（当调用者传入的是 all_vouchers 的引用时），
        或者数据源有重复记录。跳过自身可以避免误报。
        """
        for voucher in all_vouchers:
            if voucher.voucher_id == current_voucher.voucher_id:
                # 跳过自身，防止自身被标记为重复（当 all_vouchers 包含 current_voucher 时）
                continue
            if voucher.voucher_date != current_voucher.voucher_date:
                continue
            if voucher.summary != current_voucher.summary:
                continue
            if (
                abs(voucher.get_total_amount() - current_voucher.get_total_amount())
                < DUPLICATE_TOLERANCE
            ):
                return True
        return False

    def _has_blank_line_description(self, voucher) -> bool:
        """判断是否存在空分录说明。"""
        return any(not line.description.strip() for line in voucher.lines)

    def _resolve_risk_level(self, flags: list[AuditFlag]) -> str:
        """推导最终风险等级。"""
        if not flags:
            return "none"
        highest_level = 0
        for flag in flags:
            highest_level = max(highest_level, SEVERITY_ORDER.get(flag.severity, 0))
        if highest_level >= SEVERITY_ORDER["high"]:
            return "high"
        if highest_level >= SEVERITY_ORDER["medium"]:
            return "medium"
        return "low"

    def _update_voucher_status(
        self, target_vouchers: list, all_flags: list[AuditFlag]
    ) -> None:
        """按凭证分组判断并更新状态。

        每张凭证独立判断：有高危或中危标记的保持 pending，
        其余标为 reviewed。
        """
        flags_by_voucher: dict[int, list[AuditFlag]] = {}
        for flag in all_flags:
            flags_by_voucher.setdefault(flag.voucher_id, []).append(flag)

        for voucher in target_vouchers:
            voucher_flags = flags_by_voucher.get(voucher.voucher_id, [])
            needs_review = any(
                flag.severity in ("high", "medium") for flag in voucher_flags
            )
            new_status = "pending" if needs_review else "reviewed"
            self._journal_repository.update_status(
                voucher_id=voucher.voucher_id,
                status=new_status,
                reviewed_by="audit",
            )
