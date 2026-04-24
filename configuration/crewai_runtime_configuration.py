"""crewAI 运行时配置。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrewAIRuntimeConfiguration:
    """描述会计部门使用 crewAI 时的最小运行参数。

    当前项目已经迁移为 crewAI 会计部门。这里刻意只保留
    首版确实需要的开关，而不是把 crewAI 的全部能力照搬到配置层：

    1. `process` 固定默认 sequential，原因是会计核算强调可复核的步骤顺序，
       不适合在初版就让 manager 动态改写角色协作路径。
    2. `memory_enabled` 默认关闭，原因是会计事实应以本项目 SQLite 账簿为准；
       如果同时启用 crewAI 记忆，容易出现“模型记住的事实”和账簿事实冲突。
    3. `cache_enabled` 默认关闭，原因是记账/审核工具具有业务副作用或依赖最新账簿，
       不能让工具结果被运行时缓存后静默复用。
    """

    process: str = "sequential"
    memory_enabled: bool = False
    cache_enabled: bool = False
    verbose: bool = False
