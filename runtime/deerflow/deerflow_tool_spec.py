"""DeerFlow 工具规格模型。"""

from dataclasses import dataclass


WEB_TOOL_GROUP_NAME = "web"
FILE_READ_TOOL_GROUP_NAME = "file:read"
FILE_WRITE_TOOL_GROUP_NAME = "file:write"
BASH_TOOL_GROUP_NAME = "bash"
FINANCE_TOOL_GROUP_NAME = "finance"


@dataclass(frozen=True)
class DeerFlowToolSpec:
    """描述一条 DeerFlow 工具配置。

    Attributes:
        name: 工具在 DeerFlow 配置中的稳定名称。
        group: DeerFlow 配置中的工具组名称，用于按 agent 限制可见工具面。
        use_path: DeerFlow 通过 `module:variable` 解析工具时使用的导入路径。
    """

    name: str
    group: str
    use_path: str
