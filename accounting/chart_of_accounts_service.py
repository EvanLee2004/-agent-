"""会计科目服务。"""

from accounting.account_subject import AccountSubject
from accounting.accounting_error import AccountingError
from accounting.chart_of_accounts_repository import ChartOfAccountsRepository
from accounting.voucher_draft import VoucherDraft


DEFAULT_SMALL_ENTERPRISE_SUBJECTS = [
    AccountSubject("1001", "库存现金", "asset", "debit", "企业持有的现金。"),
    AccountSubject("1002", "银行存款", "asset", "debit", "企业存放在银行的款项。"),
    AccountSubject("1122", "应收账款", "asset", "debit", "因销售商品或提供劳务形成的应收款。"),
    AccountSubject("2202", "应付账款", "liability", "credit", "因采购商品或接受劳务形成的应付款。"),
    AccountSubject("2221", "应交税费", "liability", "credit", "企业按税法规定应交纳的各项税费。"),
    AccountSubject("5001", "主营业务收入", "income", "credit", "企业主营业务形成的收入。"),
    AccountSubject("5401", "主营业务成本", "cost", "debit", "主营业务对应结转的成本。"),
    AccountSubject("5603", "税金及附加", "expense", "debit", "与经营活动相关的税金及附加。"),
    AccountSubject("6601", "销售费用", "expense", "debit", "销售商品过程中发生的费用。"),
    AccountSubject("6602", "管理费用", "expense", "debit", "企业行政管理活动发生的费用。"),
    AccountSubject("6603", "财务费用", "expense", "debit", "筹资及金融活动相关费用。"),
]


class ChartOfAccountsService:
    """会计科目服务。"""

    def __init__(self, chart_of_accounts_repository: ChartOfAccountsRepository):
        self._chart_of_accounts_repository = chart_of_accounts_repository

    def initialize_default_subjects(self) -> None:
        """初始化默认科目表。"""
        self._chart_of_accounts_repository.initialize_storage()
        self._chart_of_accounts_repository.save_subjects(DEFAULT_SMALL_ENTERPRISE_SUBJECTS)

    def validate_voucher_subjects(self, voucher_draft: VoucherDraft) -> None:
        """校验凭证分录科目。

        Args:
            voucher_draft: 待入账凭证。

        Raises:
            AccountingError: 科目编码不存在或编码与名称不匹配时抛出。
        """
        for line in voucher_draft.lines:
            subject = self._chart_of_accounts_repository.get_subject_by_code(line.subject_code)
            if subject is None:
                raise AccountingError(f"未知会计科目编码: {line.subject_code}")
            if subject.name != line.subject_name:
                raise AccountingError(
                    f"科目编码与名称不匹配: {line.subject_code} 应对应 {subject.name}"
                )

    def build_subject_catalog_prompt(self) -> str:
        """构造会计科目目录提示。

        Returns:
            供模型参考的会计科目目录；无科目时返回空字符串。
        """
        subjects = self._chart_of_accounts_repository.list_subjects()
        if not subjects:
            return ""
        lines = ["可用会计科目（优先从以下列表中选择）："]
        lines.extend(
            [
                (
                    f"- {subject.code} {subject.name} | 类别: {subject.category} | "
                    f"说明: {subject.description}"
                )
                for subject in subjects
            ]
        )
        return "\n".join(lines)
