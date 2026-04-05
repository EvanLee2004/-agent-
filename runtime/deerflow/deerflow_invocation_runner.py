"""DeerFlow 调用运行器。

封装 DeerFlowClient 的创建与调用，提供请求级运行时作用域。

职责边界：
- 负责 DeerFlowClient 的创建与环境变量注入
- 提供 os.environ 现场保护（保存/恢复）
- 提供进程内全局串行锁

进程内串行保护：
- 通过 threading.Lock 实现。所有 DeerFlowInvocationRunner 实例共享同一把锁
  （锁在类属性上），确保同进程内所有 DeerFlow 调用严格串行执行。
- 这同时保护了 os.environ 快照恢复机制不被并发破坏，以及 DeerFlow client
  的 checkpoint/memory 文件不被并发写入。
- 注意：这不提供跨进程安全（如需跨进程需子进程隔离），也不解决 asyncio
  协程在单线程内切换时 contextvars 的正确传播问题（需要用户在调用侧保证）。
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from deerflow.client import DeerFlowClient
    from runtime.deerflow.deerflow_client_factory import DeerFlowClientFactory
    from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets

T = TypeVar("T")


# 类属性锁：所有 DeerFlowInvocationRunner 实例共享同一把锁。
# 进程内只有一把锁，所有 DeerFlow 调用严格串行。
# 这是"同进程串行保护"，不是多线程/多进程完全并发安全。
_GLOBAL_INVOCATION_LOCK = threading.Lock()


class DeerFlowInvocationRunner:
    """DeerFlow 调用运行器。

    封装 DeerFlowClient 的完整生命周期：创建、环境变量管理、调用、清理。
    通过全局串行锁确保同进程内所有 DeerFlow 调用严格串行执行；
    通过 os.environ 快照保存/恢复确保单个请求不会污染其他请求的环境变量。

    保护范围：
    - 全局锁：确保 DeerFlow checkpoint/memory 文件不被并发写入
    - os.environ 隔离：确保环境变量不互相泄露
    限制：
    - 不提供跨进程安全（如需跨进程需子进程隔离）
    - 不解决 asyncio 单线程内协程切换时的 contextvars 传播问题
    """

    def __init__(
        self,
        client_factory: DeerFlowClientFactory,
    ):
        """构造运行器。

        Args:
            client_factory: DeerFlow 客户端工厂。
        """
        self._client_factory = client_factory

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
        """在全局串行锁 + os.environ 隔离作用域内执行对已缓存 client 的调用。

        全局串行锁确保同一进程内所有 DeerFlow 调用严格串行执行，
        防止 os.environ 快照被并发破坏，也防止 DeerFlow checkpoint/memory
        文件被并发写入。

        与 create_and_run_client() 的区别：此方法接收已准备好的 assets 和
        已缓存的 client 实例，适用于调用方已缓存 client 实例的场景。
        这样既保留了 client 缓存，又确保每次 DeerFlow 调用使用独立的 env var 环境。

        完整生命周期：
        1. 获取全局锁
        2. 保存当前 os.environ 快照
        3. 向 os.environ 注入本请求的环境变量
        4. 执行 invocation_fn
        5. 恢复 os.environ（清理本请求的注入，不影响后续调用者）
        6. 释放全局锁

        Args:
            assets: 已通过 prepare_assets() 准备好的运行时资产。
            client: 已缓存的 DeerFlowClient 实例。
            invocation_fn: 接收该 client 并返回结果的函数。

        Returns:
            invocation_fn 的返回值。
        """
        with _GLOBAL_INVOCATION_LOCK:
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
        """在全局串行锁 + os.environ 隔离作用域内创建并执行 DeerFlowClient。

        与 run_with_isolation() 走同一把全局锁，确保同进程内所有 DeerFlow 调用
        严格串行执行，防止 os.environ 快照被并发破坏，防止 checkpoint/memory 文件
        被并发写入。

        caller 提供已准备好的 assets，不在内部再次 prepare_assets()，
        这样两条路径都使用同一份 assets，避免重复 prepare_assets() 导致语义不一致。

        完整生命周期：
        1. 获取全局锁
        2. 保存当前 os.environ 快照
        3. 向 os.environ 注入本请求的环境变量
        4. 创建 DeerFlowClient
        5. 执行 invocation_fn
        6. 恢复 os.environ（清理本请求的注入，不影响后续调用者）
        7. 释放全局锁

        Args:
            assets: 已通过 prepare_assets() 准备好的运行时资产。
            agent_name: 角色名。
            invocation_fn: 接收 DeerFlowClient 并返回结果的函数。

        Returns:
            invocation_fn 的返回值。
        """
        with _GLOBAL_INVOCATION_LOCK:
            original = self._inject_environ(assets)
            try:
                client = self._client_factory.create_client(assets, agent_name)
                return invocation_fn(client)
            finally:
                self._restore_environ(original)
