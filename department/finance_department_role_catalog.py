"""财务部门角色目录。"""

from department.finance_department_constants import DEPARTMENT_DISPLAY_NAME, SHARED_SKILL_NAMES
from department.finance_department_role import FinanceDepartmentRole
from department.roles.audit_role_definition import AuditRoleDefinition
from department.roles.bookkeeping_role_definition import BookkeepingRoleDefinition
from department.roles.cashier_role_definition import CashierRoleDefinition
from department.roles.coordinator_role_definition import CoordinatorRoleDefinition
from department.roles.policy_research_role_definition import PolicyResearchRoleDefinition
from department.roles.tax_role_definition import TaxRoleDefinition


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
            CoordinatorRoleDefinition().build(),
            CashierRoleDefinition().build(),
            BookkeepingRoleDefinition().build(),
            PolicyResearchRoleDefinition().build(),
            TaxRoleDefinition().build(),
            AuditRoleDefinition().build(),
        )
