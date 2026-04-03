"""财务部门角色模型。"""

from dataclasses import dataclass


DEFAULT_TOOL_GROUPS = ("finance",)


@dataclass(frozen=True)
class FinanceDepartmentRole:
    """描述一个财务部门角色。

    该模型是财务部门角色目录的单一事实来源。之所以把角色定义抽成独立模型，
    是为了避免角色名称、技能包名称、SOUL 说明和工具组在多个配置文件中重复维护，
    从而降低后续扩角色或调职责时的回归风险。

    Attributes:
        agent_name: DeerFlow 侧使用的 agent 名称，必须满足上游命名规则。
        display_name: 面向产品和文档展示的中文角色名。
        description: 角色职责摘要，会写入 DeerFlow agent 配置。
        skill_names: 该角色可加载的专属 skill 名称集合。
        soul_markdown: 角色的行为准则，会写入 SOUL.md。
        tool_groups: 该角色允许使用的工具组。
        is_entry_role: 是否为当前部门的默认对外入口角色。
    """

    agent_name: str
    display_name: str
    description: str
    skill_names: tuple[str, ...]
    soul_markdown: str
    tool_groups: tuple[str, ...] = DEFAULT_TOOL_GROUPS
    is_entry_role: bool = False
