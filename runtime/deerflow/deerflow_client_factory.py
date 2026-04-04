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

    并发安全说明（重要概念区分）：

    1. **文件路径隔离**：通过独立的 runtime_root，每个请求可以拥有自己的
       config.yaml / extensions_config.json / checkpoints.sqlite / home/ 目录。
       这是由 DeerFlowRuntimeAssets.runtime_root 决定的，已经可以在创建
       DepartmentOrchestrationFactory 时传入独立目录实现。

    2. **进程级环境变量隔离**：os.environ 是进程级全局状态。本工厂在
       create_client() 中向其中写入 DEER_FLOW_CONFIG_PATH /
       DEER_FLOW_EXTENSIONS_CONFIG_PATH / DEER_FLOW_HOME 以及模型 API keys。
       这些写入发生在 client 实例创建时，而非每次 reply() 时。

       两者不是一回事：即使 runtime_root 不同，写入同一进程的 os.environ
       仍然会互相覆盖。如果先创建 client_A（设置 DEER_FLOW_HOME=/tmp/a），
       再创建 client_B（设置 DEER_FLOW_HOME=/tmp/b），那么之后 client_A
       再次使用时读到的 DEER_FLOW_HOME 已经是 /tmp/b 了。

    在单线程 CLI 场景下：所有 client 创建都是串行的，不存在并发问题。
    在多线程 API 场景下：必须同时解决文件路径隔离和进程级环境变量隔离。
    当前最小落地方案是文件路径隔离；进程级环境变量污染需要：
    - 要么每个请求在独立的子进程中运行 DeerFlowClient
    - 要么在 DeerFlow 底层支持通过参数传入而非读 os.environ

    API 化之前的最小可行方案：确保每请求创建独立的 factory 实例和
    runtime_root，文件路径隔离可满足基本需求；os.environ 污染需在
    DeerFlow 底层修复或 API 入口层处理。
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
