"""DeerFlow 客户端工厂。"""

import os

from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets
from runtime.deerflow.deerflow_runtime_error import DeerFlowRuntimeError


class DeerFlowClientFactory:
    """负责创建 DeerFlow 公开客户端。

    这里单独保留工厂，而不是让仓储直接 `DeerFlowClient(...)`，
    是为了把第三方运行时的构造细节隔离出去。这样未来切换
    DeerFlow 参数、client 类型或初始化策略时，不会影响会话仓储的职责。
    """

    def create_client(
        self,
        assets: DeerFlowRuntimeAssets,
        agent_name: str,
    ):
        """构造 DeerFlowClient。

        Args:
            assets: DeerFlow 运行时本地资产。
            agent_name: 当前会话所使用的 Agent 名称。

        Returns:
            已完成配置绑定的 DeerFlowClient。
        """
        try:
            from deerflow.client import DeerFlowClient

            # DeerFlow 当前版本会在多处重新解析配置和运行目录。
            # 这里显式注入环境变量，是为了把状态根目录锁进项目自身的
            # `.runtime/deerflow/`，避免线程状态和临时文件泄漏到用户主目录。
            for env_name, env_value in assets.environment_variables.items():
                os.environ[env_name] = env_value
            os.environ["DEER_FLOW_CONFIG_PATH"] = str(assets.config_path)
            os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = str(assets.extensions_config_path)
            os.environ["DEER_FLOW_HOME"] = str(assets.runtime_home)
            runtime_configuration = assets.runtime_configuration
            return DeerFlowClient(
                config_path=str(assets.config_path),
                # 这些开关必须来自统一配置对象，而不是在工厂里写死。
                # 否则即使 `config.json` 已经声明启用 subagent / plan mode，
                # 真实运行出来的 client 仍然会悄悄退回默认值。
                thinking_enabled=runtime_configuration.thinking_enabled,
                subagent_enabled=runtime_configuration.subagent_enabled,
                plan_mode=runtime_configuration.plan_mode,
                agent_name=agent_name,
                available_skills=set(assets.available_skills),
            )
        except (FileNotFoundError, ImportError, OSError, ValueError) as error:
            raise DeerFlowRuntimeError(f"DeerFlow 客户端初始化失败: {str(error)}") from error
