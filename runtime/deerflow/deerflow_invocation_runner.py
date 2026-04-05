"""DeerFlow 调用运行器。

封装 DeerFlowClient 的创建与调用，提供请求级运行时作用域。

职责边界：
- 负责 DeerFlowClient 的创建与环境变量注入
- 提供 os.environ 现场保护（保存/恢复）

并发安全说明：
- os.environ 快照恢复：调用前后保存/恢复，确保单个请求的 DeerFlow
  调用不会污染同进程其他代码的环境变量。
- 不保证多线程并发安全（os.environ 本身不是线程安全的）。
  当前适用场景：CLI 单线程串行调用，或 API 单进程单 worker。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from deerflow.client import DeerFlowClient
    from runtime.deerflow.deerflow_client_factory import DeerFlowClientFactory
    from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets

T = TypeVar("T")


class DeerFlowInvocationRunner:
    """DeerFlow 调用运行器。

    封装 DeerFlowClient 的完整生命周期：创建、环境变量管理、调用、清理。
    通过保存/恢复 os.environ 快照，单个请求的 DeerFlow 调用不会污染同进程其他代码。

    注意：此隔离机制只缩小污染窗口，不提供多线程/多进程并发安全。
    适用场景：CLI 单线程串行调用，或 API 单进程单 worker。
    """

    def __init__(
        self,
        client_factory: DeerFlowClientFactory,
        runtime_assets_service: DeerFlowRuntimeAssetsService,
        configuration,  # LlmConfiguration，延迟避免循环依赖
    ):
        """构造运行器。

        Args:
            client_factory: DeerFlow 客户端工厂。
            runtime_assets_service: 运行时资产服务。
            configuration: LLM 配置（用于 prepare_assets）。
        """
        self._client_factory = client_factory
        self._runtime_assets_service = runtime_assets_service
        self._configuration = configuration

    def _inject_environ(self, assets: DeerFlowRuntimeAssets) -> dict[str, str]:
        """向 os.environ 注入运行时环境变量，返回原始环境快照。

        Returns:
            调用前的 os.environ 快照，用于 finally 块恢复。
        """
        original = dict(os.environ)
        for env_name, env_value in assets.environment_variables.items():
            os.environ[env_name] = env_value
        os.environ["DEER_FLOW_CONFIG_PATH"] = str(assets.config_path)
        os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = str(
            assets.extensions_config_path
        )
        os.environ["DEER_FLOW_HOME"] = str(assets.runtime_home)
        return original

    def _restore_environ(self, original: dict[str, str]) -> None:
        """恢复 os.environ 到原始状态。"""
        os.environ.clear()
        os.environ.update(original)

    def run_with_isolation(
        self,
        assets: DeerFlowRuntimeAssets,
        client: Any,
        invocation_fn: Callable[[Any], T],
    ) -> T:
        """在 os.environ 隔离作用域内执行对已缓存 client 的调用。

        与 create_and_run_client() 的区别：此方法接收已准备好的 assets 和
        已缓存的 client 实例，适用于调用方已缓存 client 实例的场景。
        这样既保留了 client 缓存，又确保每次 DeerFlow 调用使用独立的 env var 环境。

        完整生命周期：
        1. 保存当前 os.environ 快照
        2. 向 os.environ 注入本请求的环境变量
        3. 执行 invocation_fn
        4. 恢复 os.environ（清理本请求的注入，不影响后续调用者）

        Args:
            assets: 已通过 prepare_assets() 准备好的运行时资产。
            client: 已缓存的 DeerFlowClient 实例。
            invocation_fn: 接收该 client 并返回结果的函数。

        Returns:
            invocation_fn 的返回值。
        """
        original = self._inject_environ(assets)
        try:
            return invocation_fn(client)
        finally:
            self._restore_environ(original)

    def create_and_run_client(
        self,
        assets: DeerFlowRuntimeAssets,
        agent_name: str,
        invocation_fn: Callable[[Any], T],
    ) -> T:
        """创建 DeerFlowClient 并在作用域内执行调用。

        与 run_with_isolation() 语义对齐： caller 提供已准备好的 assets，
        不在内部再次 prepare_assets()。这样两条路径都使用同一份 assets，
        避免重复 prepare_assets() 导致语义不一致。

        完整生命周期：
        1. 保存当前 os.environ 快照
        2. 向 os.environ 注入本请求的环境变量
        3. 创建 DeerFlowClient
        4. 执行 invocation_fn
        5. 恢复 os.environ（清理本请求的注入，不影响后续调用者）

        Args:
            assets: 已通过 prepare_assets() 准备好的运行时资产。
            agent_name: 角色名。
            invocation_fn: 接收 DeerFlowClient 并返回结果的函数。

        Returns:
            invocation_fn 的返回值。
        """
        original = self._inject_environ(assets)
        try:
            client = self._client_factory.create_client(assets, agent_name)
            return invocation_fn(client)
        finally:
            self._restore_environ(original)
