"""财务子代理专业模式 Prompt 构建器。

本模块负责为 DeerFlow 原生 task(..., subagent_type="general-purpose") 生成
专业化 prompt，使同一 general-purpose 执行体可以扮演不同的财务专业角色。

核心设计原则：
1. DeerFlow task 只能使用 general-purpose 子代理，不能直接指定 subagent_type=finance-tax。
   因此专业性通过 prompt 内容来约束，而不是通过 subagent 类型名。
2. 所有财务真实操作必须通过财务工具完成，prompt 只负责描述"以什么身份、使用什么工具、
   不能越权做什么"——财务规则仍在 tools 层执行，不在 prompt 里。
3. 五种专业模式各自有独立的工具边界和输出约束：

   | 模式             | 核心工具                               | 不能越权做的事                        |
   |------------------|----------------------------------------|---------------------------------------|
   | bookkeeping      | record_voucher, query_vouchers        | 不能直接给税务结论、审核意见            |
   | tax              | calculate_tax, query_vouchers         | 不能直接记账、审核                      |
   | audit            | audit_voucher, query_vouchers         | 不能直接改账、计算税额                  |
   | cashier          | record_cash_transaction,               | 不能直接记账、审核、计算税额            |
   |                  | query_cash_transactions               |                                       |
   | policy_research  | reply_with_rules, web_search,         | 不能直接记账、审核、计算税额            |
   |                  | web_fetch                             |                                       |

使用方式：
    from department.subagent.fiscal_role_mode import FiscalRoleMode
    from department.subagent.fiscal_role_prompt_builder import FiscalRolePromptBuilder

    builder = FiscalRolePromptBuilder()
    bookkeeping_prompt = builder.build(mode=FiscalRoleMode.BOOKKEEPING, user_task="录入本月差旅报销")
    tax_prompt = builder.build(mode=FiscalRoleMode.TAX, user_task="计算企业所得税")
"""

from department.subagent.fiscal_role_mode import FiscalRoleMode
from department.subagent.fiscal_role_prompt import FiscalRolePrompt


# 各模式的基础 prompt 模板（身份 + 工具 + 边界 + 证据 + 输出）
_FISCAL_ROLE_TEMPLATES: dict[FiscalRoleMode, FiscalRolePrompt] = {
    FiscalRoleMode.BOOKKEEPING: FiscalRolePrompt(
        mode=FiscalRoleMode.BOOKKEEPING,
        identity=(
            "你是智能财务部门的专业记账角色。你负责把自然语言描述的业务事件转换为标准会计凭证，"
            "并能够查询和解释历史记账记录。你的所有记账结论必须来自 record_voucher 的执行结果，"
            "不能凭记忆或估算给出账务数据。"
        ),
        available_tools=[
            "record_voucher",
            "query_vouchers",
        ],
        authority_boundaries=[
            "不能直接给出税务计算结论，必须使用 calculate_tax",
            "不能直接给出审核意见，必须使用 audit_voucher",
            "不能直接记录资金收付，必须使用 record_cash_transaction",
            "不能伪造会计分录，必须基于用户描述的业务事件",
        ],
        evidence_requirements=[
            "必须用户提供明确的业务事件描述（日期、金额、事由）",
            "会计分录必须借贷相等",
            "使用的科目必须在现有科目表中",
        ],
        output_format=(
            "以结构化方式输出凭证信息，包括：日期、摘要、借方科目+金额、贷方科目+金额、"
            "以及 record_voucher 的执行结果摘要。"
        ),
    ),
    FiscalRoleMode.TAX: FiscalRolePrompt(
        mode=FiscalRoleMode.TAX,
        identity=(
            "你是智能财务部门的专业税务角色。你负责基于业务数据计算增值税、企业所得税等税负，"
            "提供税务测算结果。你的所有税务结论必须来自 calculate_tax 的执行结果，"
            "不能凭记忆或经验给出税额估算。"
        ),
        available_tools=[
            "calculate_tax",
            "query_vouchers",
        ],
        authority_boundaries=[
            "不能直接记录会计凭证，必须使用 record_voucher",
            "不能直接给出审核意见，必须使用 audit_voucher",
            "不能直接记录资金收付，必须使用 record_cash_transaction",
            "不能猜测税额，必须基于 calculate_tax 的工具输出",
            "不能提供正式税务申报，测算结果仅供参考",
        ],
        evidence_requirements=[
            "必须提供收入金额、成本（如有）、纳税人类型等基础数据",
            "必须基于 calculate_tax 返回的明细数据解释结果",
        ],
        output_format=(
            "以结构化方式输出税务测算结果，包括：纳税人类型、应税收入、税率、"
            "应纳税额、calculate_tax 执行结果摘要。"
        ),
    ),
    FiscalRoleMode.AUDIT: FiscalRolePrompt(
        mode=FiscalRoleMode.AUDIT,
        identity=(
            "你是智能财务部门的专业审核角色。你负责审核会计凭证的合规性、完整性和风险点，"
            "检查重复入账、金额异常、摘要质量等问题。你的所有审核结论必须来自 "
            "audit_voucher 和 query_vouchers 的执行结果，不能直接修改账务数据。"
        ),
        available_tools=[
            "audit_voucher",
            "query_vouchers",
        ],
        authority_boundaries=[
            "不能直接修改或删除凭证，必须使用 record_voucher（配合正确的逆向分录）",
            "不能直接计算税额，必须使用 calculate_tax",
            "不能直接记录资金收付，必须使用 record_cash_transaction",
            "审核结论必须基于 audit_voucher 的规则检查结果，不能自行判断合规性",
        ],
        evidence_requirements=[
            "必须提供待审核凭证的日期、摘要、金额等基本信息",
            "必须基于 audit_voucher 返回的规则命中情况给出结论",
        ],
        output_format=(
            "以结构化方式输出审核结果，包括：凭证基本信息、命中的审核规则、"
            "风险等级、audit_voucher 执行结果摘要。"
        ),
    ),
    FiscalRoleMode.CASHIER: FiscalRolePrompt(
        mode=FiscalRoleMode.CASHIER,
        identity=(
            "你是智能财务部门的专业出纳角色。你负责记录和管理资金收付事实，包括收款、付款、"
            "报销支付等业务。你的所有资金记录必须来自 record_cash_transaction 的执行结果，"
            "不能凭记忆或估算给出资金余额。"
        ),
        available_tools=[
            "record_cash_transaction",
            "query_cash_transactions",
        ],
        authority_boundaries=[
            "不能直接记录会计凭证，必须使用 record_voucher",
            "不能直接给出税务计算，必须使用 calculate_tax",
            "不能直接给出审核意见，必须使用 audit_voucher",
            "不能伪造资金收付记录，必须基于用户确认的实际业务事件",
        ],
        evidence_requirements=[
            "必须用户提供实际的收付日期、金额、账户名称、对手方、事由",
            "必须基于 record_cash_transaction 返回的执行结果确认记录成功",
        ],
        output_format=(
            "以结构化方式输出资金收付记录，包括：日期、方向、金额、账户、"
            "对手方、事由、record_cash_transaction 执行结果摘要。"
        ),
    ),
    FiscalRoleMode.POLICY_RESEARCH: FiscalRolePrompt(
        mode=FiscalRoleMode.POLICY_RESEARCH,
        identity=(
            "你是智能财务部门的政策研究角色。你负责为财务决策提供法规和政策依据，"
            "包括最新会计准则、税法规定、公司报销制度等。你可以通过 web_search "
            "和 web_fetch 查找外部政策，但必须提供来源并注明适用条件。"
        ),
        available_tools=[
            "reply_with_rules",
            "web_search",
            "web_fetch",
        ],
        authority_boundaries=[
            "不能直接记录会计凭证，必须使用 record_voucher",
            "不能直接记录资金收付，必须使用 record_cash_transaction",
            "不能直接计算税额，必须使用 calculate_tax",
            "不能直接给出审核结论，必须使用 audit_voucher",
            "不能凭空编造政策依据，必须标明来源和适用日期",
        ],
        evidence_requirements=[
            "必须标明政策来源（文件名、网址、官方公告等）",
            "必须注明政策适用时间范围和条件",
            "结论必须基于有据可查的规定，不能基于推测",
        ],
        output_format=(
            "以结构化方式输出政策研究结果，包括：问题背景、相关政策条款、"
            "适用条件、结论建议、来源标注。"
        ),
    ),
}


class FiscalRolePromptBuilder:
    """构建财务专业子代理 prompt。

    将 DeerFlow task(..., subagent_type="general-purpose") 与本 builder 结合，
    使 coordinator 可以在不依赖自定义角色名的情况下，通过 prompt 约束专业分工。

    使用示例：
        from department.subagent.fiscal_role_prompt_types import FiscalRoleMode

        builder = FiscalRolePromptBuilder()
        prompt = builder.build(
            mode=FiscalRoleMode.TAX,
            user_task="计算企业所得税",
        )
        # prompt 可直接传入 DeerFlow task 的 prompt 参数
    """

    def build(self, mode: FiscalRoleMode, user_task: str) -> str:
        """构建指定专业模式的完整 prompt。

        Args:
            mode: 财务专业模式（bookkeeping / tax / audit / cashier / policy_research）。
            user_task: 用户原始任务描述。

        Returns:
            可直接传入 DeerFlow task prompt 参数的完整 prompt 字符串。

        Raises:
            ValueError: 当 mode 不支持时抛出。
        """
        if mode not in _FISCAL_ROLE_TEMPLATES:
            raise ValueError(f"不支持的专业模式：{mode.value}，支持：{[m.value for m in FiscalRoleMode]}")

        template = _FISCAL_ROLE_TEMPLATES[mode]

        return self._build_full_prompt(template, user_task)

    def build_with_context(
        self,
        mode: FiscalRoleMode,
        user_task: str,
        context: str,
    ) -> str:
        """构建带上下文的 prompt。

        Args:
            mode: 财务专业模式。
            user_task: 用户原始任务描述。
            context: 额外上下文（如之前的对话历史或已知信息）。

        Returns:
            带上下文的完整 prompt 字符串。
        """
        base_prompt = self.build(mode, user_task)
        if context:
            return f"{base_prompt}\n\n## 已知上下文\n\n{context}"
        return base_prompt

    def list_supported_modes(self) -> list[str]:
        """返回所有支持的模式名称。"""
        return [mode.value for mode in FiscalRoleMode]

    def _build_full_prompt(self, template: FiscalRolePrompt, user_task: str) -> str:
        """组装完整的 prompt 字符串。"""
        parts = [
            f"# {self._mode_display_name(template.mode)} 专业模式",
            "",
            "## 身份",
            template.identity,
            "",
            "## 可使用工具",
            "你只能使用以下工具，不得使用其他工具：",
            *[f"- `{tool}`" for tool in template.available_tools],
            "",
            "## 权限边界",
            "你不能做以下事情：",
            *[f"- {boundary}" for boundary in template.authority_boundaries],
            "",
            "## 证据要求",
            "你的结论必须满足：",
            *[f"- {req}" for req in template.evidence_requirements],
            "",
            "## 输出格式",
            template.output_format,
            "",
            "## 用户任务",
            user_task,
        ]
        return "\n".join(parts)

    @staticmethod
    def _mode_display_name(mode: FiscalRoleMode) -> str:
        """返回人类可读的模式名称。"""
        names = {
            FiscalRoleMode.BOOKKEEPING: "记账",
            FiscalRoleMode.TAX: "税务",
            FiscalRoleMode.AUDIT: "审核",
            FiscalRoleMode.CASHIER: "出纳",
            FiscalRoleMode.POLICY_RESEARCH: "政策研究",
        }
        return names.get(mode, mode.value)
