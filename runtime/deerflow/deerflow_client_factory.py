"""DeerFlow 客户端工厂。"""

import os
import sqlite3
from typing import TYPE_CHECKING

from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets
from runtime.deerflow.deerflow_runtime_error import DeerFlowRuntimeError

if TYPE_CHECKING:
    from deerflow.client import DeerFlowClient


class DeerFlowClientFactory:
    """负责创建 DeerFlow 公开客户端。

    这里单独保留工厂，而不是让仓储直接 `DeerFlowClient(...)`，
    是为了把第三方运行时的构造细节隔离出去。这样未来切换
    DeerFlow 参数、client 类型或初始化策略时，不会影响会话仓储的职责。

    checkpointer 由工厂程序化创建（而非从 config.yaml 读取），原因是
    connection_string 是机器级绝对路径，放进静态 config.yaml 会使其不可跨机器复用。
    通过 DeerFlowClient(checkpointer=...) 直接注入，config.yaml 无需 checkpointer 段。
    """

    def create_client(
        self,
        assets: DeerFlowRuntimeAssets,
        agent_name: str,
    ) -> "DeerFlowClient":
        """构造 DeerFlowClient，并注入运行时环境变量和 checkpointer。

        Args:
            assets: DeerFlow 运行时本地资产。
            agent_name: 当前会话所使用的 Agent 名称。

        Returns:
            已完成配置绑定的 DeerFlowClient。
        """
        try:
            from deerflow.client import DeerFlowClient
            from langgraph.checkpoint.sqlite import SqliteSaver

            # DeerFlow 读取 config.yaml 时通过 resolve_env_variables() 展开 $VAR 占位符，
            # 因此必须在创建 client 前注入环境变量。当通过 DeerFlowInvocationRunner
            # 调用时，runner 的 _inject_environ() 已提前注入且会在调用结束后恢复；
            # 此处注入是为了支持不经过 runner 直接调用工厂的场景（如测试）。
            for env_name, env_value in assets.environment_variables.items():
                os.environ[env_name] = env_value
            os.environ["DEER_FLOW_CONFIG_PATH"] = str(assets.config_path)
            os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = str(
                assets.extensions_config_path
            )
            os.environ["DEER_FLOW_HOME"] = str(assets.runtime_home)

            # 程序化创建 SQLite checkpointer，避免把绝对路径写入静态 config.yaml
            checkpoint_path = assets.runtime_root / "checkpoints.sqlite"
            conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
            checkpointer = SqliteSaver(conn)

            runtime_configuration = assets.runtime_configuration
            return DeerFlowClient(
                config_path=str(assets.config_path),
                checkpointer=checkpointer,
                thinking_enabled=runtime_configuration.thinking_enabled,
                subagent_enabled=runtime_configuration.subagent_enabled,
                plan_mode=runtime_configuration.plan_mode,
                agent_name=agent_name,
                available_skills=set(assets.available_skills),
            )
        except (FileNotFoundError, ImportError, OSError, ValueError) as error:
            raise DeerFlowRuntimeError(
                f"DeerFlow 客户端初始化失败: {str(error)}"
            ) from error
