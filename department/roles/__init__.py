"""财务部门角色注册表。

当前 Python 侧只需要维护三类最小角色元数据：
1. DeerFlow agent_name
2. 角色专属 skill_names
3. 是否为入口角色

description、tool_groups、SOUL.md 都已经迁移到
.agent_assets/deerflow_config/home/agents/<agent_name>/ 下的静态文件，
继续为每个角色单独保留一个只有 build() 的定义类，只会增加文件数量和跳转成本，
不会提供额外业务价值。

因此这里把默认角色集合压成一个静态注册表，作为 FinanceDepartmentRoleCatalog
的默认输入。这样既保留 `department/roles/` 作为角色边界目录，又避免六个样板类
继续承担“为了分层而分层”的过渡职责。
"""

from department.finance_department_role import FinanceDepartmentRole


DEFAULT_DEPARTMENT_ROLES: tuple[FinanceDepartmentRole, ...] = (
    FinanceDepartmentRole(
        agent_name="finance-coordinator",
        skill_names=("coordinator",),
        is_entry_role=True,
    ),
    FinanceDepartmentRole(
        agent_name="finance-cashier",
        skill_names=("cashier",),
    ),
    FinanceDepartmentRole(
        agent_name="finance-bookkeeping",
        skill_names=("bookkeeping",),
    ),
    FinanceDepartmentRole(
        agent_name="finance-policy-research",
        skill_names=("policy-research",),
    ),
    FinanceDepartmentRole(
        agent_name="finance-tax",
        skill_names=("tax",),
    ),
    FinanceDepartmentRole(
        agent_name="finance-audit",
        skill_names=("audit",),
    ),
)
