"""DeerFlow 客户端工厂。"""

import os
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

    并发安全说明：
    os.environ 是进程级全局状态。本工厂在 create_client() 中向其中写入
    DEER_FLOW_CONFIG_PATH / DEER_FLOW_EXTENSIONS_CONFIG_PATH / DEER_FLOW_HOME
    以及模型 API keys。这些写入发生在 client 实例创建时，而非每次 reply() 时。

    在单线程 CLI 场景下：所有 client 创建都是串行的，不存在并发问题。
    在多线程 API 场景下：不同线程同时调用 create_client() 会互相覆盖对方的
    环境变量，可能导致某线程的 client 用错了另一线程的配置。

    当前最小修复方案：
    - 在注释中记录此风险，不做大规模重构
    - 未来 API 化时，应让每个请求/线程拥有独立的 runtime_root（通过参数传入），
      而不是在工厂里用全局 .runtime/deerflow/
    - 环境变量污染风险在 API 并发场景下会被放大，需要在 API 入口层做隔离
    """

    def create_client(
        self,
        assets: DeerFlowRuntimeAssets,
        agent_name: str,
    ) -> "DeerFlowClient":
        """构造 DeerFlowClient。

        Args:
            assets: DeerFlow 运行时本地资产。
            agent_name: 当前会话所使用的 Agent 名称。

        Returns:
            已完成配置绑定的 DeerFlowClient。

        Note:
            该方法会向 os.environ 写入环境变量。在并发场景下，
            调用方应确保不同请求拥有独立的 assets（特别是 runtime_home）。
        """
        try:
            from deerflow.client import DeerFlowClient

            # DeerFlow 当前版本会在多处重新解析配置和运行目录。
            # 这里显式注入环境变量，是为了把状态根目录锁进项目自身的
            # `.runtime/deerflow/`，避免线程状态和临时文件泄漏到用户主目录。
            #
            # 风险提示：os.environ 是进程级全局变量，多线程并发写入会互相覆盖。
            # 当前 CLI 是单线程，故无影响；API 场景需要请求级隔离。
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
