"""DeerFlow 运行时资产模型。"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeerFlowRuntimeAssets:
    """描述 DeerFlow 运行时需要消费的本地资产。

    Attributes:
        config_path: DeerFlow 主配置文件路径。
        extensions_config_path: DeerFlow 扩展配置文件路径。
        runtime_home: DeerFlow 运行期状态根目录。
        skills_path: DeerFlow skills 根目录路径。
        available_skills: 当前运行时允许暴露给 Agent 的 skill 名称集合。
        api_key: 运行时需要注入 DeerFlow 环境的 API Key。
    """

    config_path: Path
    extensions_config_path: Path
    runtime_home: Path
    skills_path: Path
    available_skills: set[str]
    api_key: str
