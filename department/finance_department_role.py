"""财务部门角色模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FinanceDepartmentRole:
    """描述一个财务部门角色。

    该模型是财务部门角色目录的单一事实来源。之所以把角色定义抽成独立模型，
    是为了避免角色名称、入口属性和 skill 名称在多个模块中重复维护，
    从而降低后续扩角色或调职责时的回归风险。

    Attributes:
        agent_name: DeerFlow 侧使用的 agent 名称，必须满足上游命名规则。
        skill_names: 该角色可加载的专属 skill 名称集合。
        is_entry_role: 是否为当前部门的默认对外入口角色。

    设计边界：
    - agent 的 description、tool_groups、SOUL.md 已迁移到
      .agent_assets/deerflow_config/home/agents/<agent_name>/ 下的静态文件，
      Python 侧不再重复维护这些字段，避免出现“两份角色事实来源”。
    - 因此本模型只保留部门编排层真正需要的最小角色元数据。
    """

    agent_name: str
    skill_names: tuple[str, ...]
    is_entry_role: bool = False
