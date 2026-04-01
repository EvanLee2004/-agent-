"""会计科目应用服务。

该服务负责：
1. 初始化小企业会计系统需要的基础科目表。
2. 校验凭证中的科目是否合法。
3. 为 accounting skill 提供明确的科目目录，降低模型胡编科目的概率。
"""

from domain.models import AccountSubject, VoucherDraft
from infrastructure.accounting_repository import IChartOfAccountsRepository


DEFAULT_SMALL_ENTERPRISE_SUBJECTS = [
    AccountSubject(
        code="1001",
        name="库存现金",
        category="asset",
        normal_balance="debit",
        description="企业持有的现金。",
    ),
    AccountSubject(
        code="1002",
        name="银行存款",
        category="asset",
        normal_balance="debit",
        description="企业存放在银行的款项。",
    ),
    AccountSubject(
        code="1122",
        name="应收账款",
        category="asset",
        normal_balance="debit",
        description="因销售商品或提供劳务形成的应收款。",
    ),
    AccountSubject(
        code="2202",
        name="应付账款",
        category="liability",
        normal_balance="credit",
        description="因采购商品或接受劳务形成的应付款。",
    ),
    AccountSubject(
        code="2221",
        name="应交税费",
        category="liability",
        normal_balance="credit",
        description="企业按税法规定应交纳的各项税费。",
    ),
    AccountSubject(
        code="5001",
        name="主营业务收入",
        category="income",
        normal_balance="credit",
        description="企业主营业务形成的收入。",
    ),
    AccountSubject(
        code="5401",
        name="主营业务成本",
        category="cost",
        normal_balance="debit",
        description="主营业务对应结转的成本。",
    ),
    AccountSubject(
        code="5603",
        name="税金及附加",
        category="expense",
        normal_balance="debit",
        description="与经营活动相关的税金及附加。",
    ),
    AccountSubject(
        code="6601",
        name="销售费用",
        category="expense",
        normal_balance="debit",
        description="销售商品过程中发生的费用。",
    ),
    AccountSubject(
        code="6602",
        name="管理费用",
        category="expense",
        normal_balance="debit",
        description="企业行政管理活动发生的费用。",
    ),
    AccountSubject(
        code="6603",
        name="财务费用",
        category="expense",
        normal_balance="debit",
        description="筹资及金融活动相关费用。",
    ),
]


class ChartOfAccountsService:
    """会计科目应用服务。"""

    def __init__(self, repository: IChartOfAccountsRepository):
        self._repository = repository

    def initialize_default_subjects(self) -> None:
        """初始化默认科目表。

        这里显式在应用层完成初始化，而不是把业务知识塞进 Repository。
        这样一来：
        - Repository 只关心数据库读写
        - 哪些科目属于“默认业务配置”由 Service 决定
        """
        self._repository.init_db()
        self._repository.upsert_subjects(DEFAULT_SMALL_ENTERPRISE_SUBJECTS)

    def validate_voucher_subjects(self, voucher: VoucherDraft) -> None:
        """校验凭证中的全部科目。

        同时校验编码和名称，是为了减少“模型写对了名称但写错编码”
        或“编码正确但名称张冠李戴”的情况。
        """
        for line in voucher.lines:
            subject = self._repository.get_by_code(line.subject_code)
            if subject is None:
                raise ValueError(f"未知会计科目编码: {line.subject_code}")
            if subject.name != line.subject_name:
                raise ValueError(
                    f"科目编码与名称不匹配: {line.subject_code} 对应 {subject.name}，而不是 {line.subject_name}"
                )

    def build_subject_catalog_prompt(self) -> str:
        """构造供 accounting skill 使用的科目目录说明。"""
        subjects = self._repository.list_subjects()
        if not subjects:
            return ""

        lines = ["可用会计科目（优先从以下列表中选择）："]
        for subject in subjects:
            lines.append(
                f"- {subject.code} {subject.name} | 类别: {subject.category} | 说明: {subject.description}"
            )
        return "\n".join(lines)
