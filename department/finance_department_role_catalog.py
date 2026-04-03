"""财务部门角色目录。"""

from department.finance_department_role import FinanceDepartmentRole


DEPARTMENT_DISPLAY_NAME = "智能财务部门"
SHARED_SKILL_NAMES = ("finance-core",)


class FinanceDepartmentRoleCatalog:
    """提供财务部门角色与技能的统一目录。

    这里使用目录对象而不是在多个模块里散落常量，是为了把“部门有哪些角色、
    哪些 skill 属于共享能力、哪个角色是入口角色”集中管理。这样 DeerFlow
    资产生成、依赖注入和后续角色编排都能共享同一份定义，避免角色信息分叉。
    """

    def __init__(
        self,
        roles: tuple[FinanceDepartmentRole, ...] | None = None,
        department_display_name: str = DEPARTMENT_DISPLAY_NAME,
        shared_skill_names: tuple[str, ...] = SHARED_SKILL_NAMES,
    ):
        self._roles = roles or self._build_default_roles()
        self._department_display_name = department_display_name
        self._shared_skill_names = shared_skill_names

    def get_department_display_name(self) -> str:
        """获取部门展示名称。

        Returns:
            产品侧统一使用的部门展示名。
        """
        return self._department_display_name

    def get_entry_role(self) -> FinanceDepartmentRole:
        """获取默认入口角色。

        Returns:
            当前部门的默认入口角色。

        Raises:
            ValueError: 当角色目录里没有唯一入口角色时抛出。
        """
        entry_roles = [role for role in self._roles if role.is_entry_role]
        if len(entry_roles) != 1:
            raise ValueError("财务部门必须且只能定义一个入口角色")
        return entry_roles[0]

    def get_role(self, agent_name: str) -> FinanceDepartmentRole:
        """按 agent 名称获取角色定义。

        Args:
            agent_name: DeerFlow 侧 agent 名称。

        Returns:
            对应的角色定义。

        Raises:
            KeyError: 角色不存在时抛出。
        """
        for role in self._roles:
            if role.agent_name == agent_name:
                return role
        raise KeyError(f"未找到财务部门角色: {agent_name}")

    def list_roles(self) -> tuple[FinanceDepartmentRole, ...]:
        """获取所有角色定义。

        Returns:
            财务部门角色元组。
        """
        return self._roles

    def list_available_skill_names(self) -> set[str]:
        """获取当前部门需要暴露给 DeerFlow 的全部 skill。

        Returns:
            共享 skill 与角色 skill 的并集。
        """
        skill_names = set(self._shared_skill_names)
        for role in self._roles:
            skill_names.update(role.skill_names)
        return skill_names

    def list_shared_skill_names(self) -> tuple[str, ...]:
        """获取共享 skill 列表。

        Returns:
            当前部门所有角色共享的 skill 名称。
        """
        return self._shared_skill_names

    def _build_default_roles(self) -> tuple[FinanceDepartmentRole, ...]:
        """构造默认财务部门角色集合。"""
        return (
            self._build_coordinator_role(),
            self._build_cashier_role(),
            self._build_bookkeeping_role(),
            self._build_policy_research_role(),
            self._build_tax_role(),
            self._build_audit_role(),
        )

    def _build_coordinator_role(self) -> FinanceDepartmentRole:
        """构造协调角色。"""
        return FinanceDepartmentRole(
            agent_name="finance-coordinator",
            display_name="CoordinatorAgent",
            description="负责理解用户需求、拆分任务、协调部门角色并汇总最终回复。",
            skill_names=("coordinator",),
            soul_markdown=self._build_coordinator_soul(),
            is_entry_role=True,
        )

    def _build_bookkeeping_role(self) -> FinanceDepartmentRole:
        """构造记账角色。"""
        return FinanceDepartmentRole(
            agent_name="finance-bookkeeping",
            display_name="BookkeepingAgent",
            description="负责凭证生成、分录落账、账目查询和会计口径收口。",
            skill_names=("bookkeeping",),
            soul_markdown=self._build_bookkeeping_soul(),
        )

    def _build_cashier_role(self) -> FinanceDepartmentRole:
        """构造出纳角色。"""
        return FinanceDepartmentRole(
            agent_name="finance-cashier",
            display_name="CashierAgent",
            description="负责资金收付事实确认、账户收付状态和报销支付结果记录。",
            skill_names=("cashier",),
            soul_markdown=self._build_cashier_soul(),
        )

    def _build_policy_research_role(self) -> FinanceDepartmentRole:
        """构造政策研究角色。"""
        return FinanceDepartmentRole(
            agent_name="finance-policy-research",
            display_name="PolicyResearchAgent",
            description="负责检索最新财税政策、准则口径和外部实时事实。",
            skill_names=("policy-research",),
            soul_markdown=self._build_policy_research_soul(),
        )

    def _build_tax_role(self) -> FinanceDepartmentRole:
        """构造税务角色。"""
        return FinanceDepartmentRole(
            agent_name="finance-tax",
            display_name="TaxAgent",
            description="负责税额测算、税前准备和口径说明，不直接执行报税。",
            skill_names=("tax",),
            soul_markdown=self._build_tax_soul(),
        )

    def _build_audit_role(self) -> FinanceDepartmentRole:
        """构造审核角色。"""
        return FinanceDepartmentRole(
            agent_name="finance-audit",
            display_name="AuditAgent",
            description="负责凭证复核、风险识别、异常解释和整改建议。",
            skill_names=("audit",),
            soul_markdown=self._build_audit_soul(),
        )

    def _build_coordinator_soul(self) -> str:
        """生成协调角色的 SOUL 内容。"""
        return (
            "# Finance Coordinator\n\n"
            "你是智能财务部门的协调中枢。财务部门当前包含 CoordinatorAgent、"
            "CashierAgent、BookkeepingAgent、PolicyResearchAgent、TaxAgent 和 AuditAgent。"
            "你的职责是理解用户目标、判断是否需要研究、记账、审核或税务处理，并把结果组织成"
            "最终回复。\n\n"
            "你不直接伪造财务事实，也不假装已经完成子角色应做的工作。若事实依赖工具、"
            "政策或账务记录，必须先让相应角色或工具提供证据。若用户出现身份介绍类问题，"
            "优先从智能财务部门整体视角展开，再自然说明你是其中的协调角色。"
        )

    def _build_bookkeeping_soul(self) -> str:
        """生成记账角色的 SOUL 内容。"""
        return (
            "# Finance Bookkeeping\n\n"
            "你是财务部门中的记账会计。你知道部门里还有 CoordinatorAgent、CashierAgent、"
            "PolicyResearchAgent、TaxAgent 和 AuditAgent。你的职责是把业务描述转换成合规凭证、查询历史账目，"
            "并在信息缺失时明确指出缺口。你必须保持借贷平衡、科目合规、摘要专业。若需要"
            "确认资金是否已经实际支付或收到，请优先请求 CashierAgent 提供事实。若用户出现"
            "身份介绍类问题，应自然说明你是智能财务部门中的记账角色，而不是整个部门。"
        )

    def _build_cashier_soul(self) -> str:
        """生成出纳角色的 SOUL 内容。"""
        return (
            "# Finance Cashier\n\n"
            "你是财务部门中的出纳角色。你知道部门里还有 CoordinatorAgent、BookkeepingAgent、"
            "PolicyResearchAgent、TaxAgent 和 AuditAgent。你的职责是确认资金是否已收付、使用了什么账户、"
            "何时发生支付，以及当前是否存在待支付事实。你只维护资金事实，不直接生成会计分录。"
            "若用户出现身份介绍类问题，应自然说明你是智能财务部门中的出纳角色，而不是整个部门。"
        )

    def _build_policy_research_soul(self) -> str:
        """生成政策研究角色的 SOUL 内容。"""
        return (
            "# Finance Policy Research\n\n"
            "你负责外部政策与准则研究。你知道部门里还有 CoordinatorAgent、CashierAgent、"
            "BookkeepingAgent、TaxAgent 和 AuditAgent。你的结论必须包含时间、来源和适用范围；若当前系统"
            "没有足够证据，你应明确说明不确定性，而不是凭记忆补全最新政策。必要时可以"
            "把研究结果提供给 TaxAgent、AuditAgent 或 CoordinatorAgent。若用户出现身份介绍类问题，"
            "应自然说明你是智能财务部门中的政策研究角色，而不是整个部门。"
        )

    def _build_tax_soul(self) -> str:
        """生成税务角色的 SOUL 内容。"""
        return (
            "# Finance Tax Preparation\n\n"
            "你负责税额测算和税前准备。你知道部门里还有 CoordinatorAgent、CashierAgent、"
            "BookkeepingAgent、PolicyResearchAgent 和 AuditAgent。你基于已入账事实、政策依据和明确口径工作。你不能把"
            "税前测算描述成正式税务申报，也不能在事实不充分时伪造税额。若政策口径不明确，"
            "请请求 PolicyResearchAgent；若账务事实不完整，请请求 BookkeepingAgent。若用户出现"
            "身份介绍类问题，应自然说明你是智能财务部门中的税前准备角色，而不是整个部门。"
        )

    def _build_audit_soul(self) -> str:
        """生成审核角色的 SOUL 内容。"""
        return (
            "# Finance Audit\n\n"
            "你负责复核财务结果，寻找异常、重复、口径冲突和风险点。你知道部门里还有"
            "CoordinatorAgent、CashierAgent、BookkeepingAgent、PolicyResearchAgent 和 TaxAgent。你的任务是帮助部门发现"
            "问题并提出整改建议，而不是为了给出结论而忽略证据不足。若发现资金事实缺失，"
            "应请求 CashierAgent；若发现账务基础不完整，应请求 BookkeepingAgent。若用户出现"
            "身份介绍类问题，应自然说明你是智能财务部门中的审核角色，而不是整个部门。"
        )
