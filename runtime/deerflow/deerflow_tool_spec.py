"""DeerFlow 工具规格模型。"""

from dataclasses import dataclass


DEERFLOW_TOOL_GROUP_NAME = "finance"


@dataclass(frozen=True)
class DeerFlowToolSpec:
    """描述一条 DeerFlow 工具配置。

    Attributes:
        name: 工具在 DeerFlow 配置中的稳定名称。
        use_path: DeerFlow 通过 `module:variable` 解析工具时使用的导入路径。
    """

    name: str
    use_path: str
