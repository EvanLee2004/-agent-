"""会计部门角色目录。"""

from department.accounting_department_role import AccountingDepartmentRole


_DEPARTMENT_DISPLAY_NAME = "智能财务部门"


class AccountingDepartmentRoleCatalog:
    """提供当前会计部门的角色目录。"""

    def __init__(self):
        self._roles = (
            AccountingDepartmentRole("accounting-manager", is_entry_role=True),
            AccountingDepartmentRole("voucher-accountant"),
            AccountingDepartmentRole("cashier-agent"),
            AccountingDepartmentRole("ledger-reviewer"),
        )

    def get_department_display_name(self) -> str:
        """获取部门展示名称。"""
        return _DEPARTMENT_DISPLAY_NAME

    def get_entry_role(self) -> AccountingDepartmentRole:
        """获取唯一入口角色。"""
        entry_roles = [role for role in self._roles if role.is_entry_role]
        if len(entry_roles) != 1:
            raise ValueError("会计部门必须且只能定义一个入口角色")
        return entry_roles[0]

    def list_roles(self) -> tuple[AccountingDepartmentRole, ...]:
        """列出全部会计部门角色。"""
        return self._roles
