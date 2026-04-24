"""会计部门角色模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountingDepartmentRole:
    """描述会计部门中的一个 crewAI 角色。

    Python 侧只维护角色名和入口标记；具体目标、背景和工具权限在 crewAI
    runtime 仓储中集中构造，避免角色事实分散在静态资产、配置文件和代码多处。
    """

    agent_name: str
    is_entry_role: bool = False
