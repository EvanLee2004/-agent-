"""DeerFlow 运行时资产模型。"""

from dataclasses import dataclass
from pathlib import Path

from configuration.deerflow_runtime_configuration import DeerFlowRuntimeConfiguration


@dataclass(frozen=True)
class DeerFlowRuntimeAssets:
    """描述 DeerFlow 运行时需要消费的本地资产。

    Attributes:
        runtime_root: DeerFlow 运行期状态根目录（包含 config、checkpoint、home）。
            这是实例级隔离的关键边界：每个并发请求/用户应拥有独立的 runtime_root。
        config_path: DeerFlow 主配置文件路径。
        extensions_config_path: DeerFlow 扩展配置文件路径。
        runtime_home: DeerFlow 运行期状态根目录（memory 等）。
        skills_path: DeerFlow skills 根目录路径。
        available_skills: 当前运行时允许暴露给 Agent 的 skill 名称集合。
        environment_variables: 运行时需要注入 DeerFlow 进程环境的变量集合。
        runtime_configuration: 当前 DeerFlow runtime 开关配置。
    """

    runtime_root: Path
    config_path: Path
    extensions_config_path: Path
    runtime_home: Path
    skills_path: Path
    available_skills: set[str]
    environment_variables: dict[str, str]
    runtime_configuration: DeerFlowRuntimeConfiguration
