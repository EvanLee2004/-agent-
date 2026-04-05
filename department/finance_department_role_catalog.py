"""财务部门角色目录。"""

from department.finance_department_role import FinanceDepartmentRole
from department.roles import DEFAULT_DEPARTMENT_ROLES

_DEPARTMENT_DISPLAY_NAME = "智能财务部门"
_SHARED_SKILL_NAMES = ("finance-core",)


class FinanceDepartmentRoleCatalog:
    """提供财务部门角色与技能的统一目录。

    这里使用目录对象而不是在多个模块里散落常量，是为了把“部门有哪些角色、
    哪些 skill 属于共享能力、哪个角色是入口角色”集中管理。这样 DeerFlow
    资产生成、依赖注入和后续角色编排都能共享同一份定义，避免角色信息分叉。
    """

    def __init__(self):
        """构造默认角色目录。

        当前系统没有“按请求替换角色注册表”的真实需求：
        - 入口角色固定是 finance-coordinator
        - 共享 skill 固定是 finance-core
        - 六个财务角色也已经与静态 DeerFlow agent 配置对齐

        因此这里不再保留 roles / department_display_name / shared_skill_names 的
        可注入构造参数，避免目录对象继续暴露没人使用的扩展面。
        """
        self._roles = DEFAULT_DEPARTMENT_ROLES
        self._department_display_name = _DEPARTMENT_DISPLAY_NAME
        self._shared_skill_names = _SHARED_SKILL_NAMES

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

    def list_available_skill_names(self) -> set[str]:
        """获取当前部门需要暴露给 DeerFlow 的全部 skill。

        Returns:
            共享 skill 与角色 skill 的并集。
        """
        skill_names = set(self._shared_skill_names)
        for role in self._roles:
            skill_names.update(role.skill_names)
        return skill_names
