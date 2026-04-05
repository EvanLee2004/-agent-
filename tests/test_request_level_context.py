"""请求级上下文隔离与运行时资产隔离测试。

验证三个核心隔离机制：
1. FinanceDepartmentToolContextRegistry.open_context_scope() 实现请求级上下文生命周期
2. 独立 runtime_root 导致 DeerFlow 运行时资产隔离
3. DeerFlowInvocationRunner 的全局锁确保同进程内调用严格串行
"""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from runtime.deerflow.deerflow_invocation_runner import DeerFlowInvocationRunner
from runtime.deerflow.deerflow_runtime_assets_service import (
    DeerFlowRuntimeAssetsService,
)
from runtime.deerflow.finance_department_tool_context import (
    FinanceDepartmentToolContext,
)
from runtime.deerflow.finance_department_tool_context_registry import (
    FinanceDepartmentToolContextRegistry,
)
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from configuration.llm_model_profile import LlmModelProfile


class TestRequestLevelContextScope(unittest.TestCase):
    """验证 open_context_scope 实现请求级上下文生命周期。"""

    def setUp(self):
        # 每个测试前重置全局状态，避免跨测试泄露
        FinanceDepartmentToolContextRegistry.reset()

    def tearDown(self):
        FinanceDepartmentToolContextRegistry.reset()

    def test_context_set_within_scope(self):
        """验证上下文在 scope 内可用。"""
        fake_context = MagicMock(spec=FinanceDepartmentToolContext)
        with FinanceDepartmentToolContextRegistry.open_context_scope(fake_context):
            result = FinanceDepartmentToolContextRegistry.get_context()
        self.assertIs(result, fake_context)

    def test_context_reset_after_scope(self):
        """验证 scope 结束后上下文被重置。"""
        fake_context = MagicMock(spec=FinanceDepartmentToolContext)
        with FinanceDepartmentToolContextRegistry.open_context_scope(fake_context):
            pass  # scope 结束
        # scope 结束后访问应抛出 RuntimeError
        with self.assertRaises(RuntimeError) as ctx:
            FinanceDepartmentToolContextRegistry.get_context()
        self.assertIn("尚未注册", str(ctx.exception))

    def test_nested_scopes_isolated(self):
        """验证嵌套 scope 的内层上下文被正确恢复。"""
        context_a = MagicMock(spec=FinanceDepartmentToolContext)
        context_b = MagicMock(spec=FinanceDepartmentToolContext)
        with FinanceDepartmentToolContextRegistry.open_context_scope(context_a):
            self.assertIs(FinanceDepartmentToolContextRegistry.get_context(), context_a)
            with FinanceDepartmentToolContextRegistry.open_context_scope(context_b):
                self.assertIs(
                    FinanceDepartmentToolContextRegistry.get_context(), context_b
                )
            # 嵌套 scope 退出后恢复为外层上下文
            self.assertIs(FinanceDepartmentToolContextRegistry.get_context(), context_a)
        # 最外层 scope 退出后被重置
        with self.assertRaises(RuntimeError):
            FinanceDepartmentToolContextRegistry.get_context()

    def test_sequential_requests_do_not_leak(self):
        """验证顺序请求之间上下文不泄露。"""
        contexts = [MagicMock(spec=FinanceDepartmentToolContext) for _ in range(3)]
        for ctx in contexts:
            with FinanceDepartmentToolContextRegistry.open_context_scope(ctx):
                self.assertIs(FinanceDepartmentToolContextRegistry.get_context(), ctx)
            # 每个请求结束后上下文的 scope 都会重置
        with self.assertRaises(RuntimeError):
            FinanceDepartmentToolContextRegistry.get_context()


class TestRuntimeRootIsolation(unittest.TestCase):
    """验证独立 runtime_root 导致文件级隔离。"""

    def test_different_runtime_roots_produce_different_assets(self):
        """验证两个不同的 runtime_root 产生独立的资产路径。"""
        with (
            tempfile.TemporaryDirectory() as tmp_a,
            tempfile.TemporaryDirectory() as tmp_b,
        ):
            root_a = Path(tmp_a) / "deerflow_a"
            root_b = Path(tmp_b) / "deerflow_b"
            catalog = FinanceDepartmentRoleCatalog()

            service_a = DeerFlowRuntimeAssetsService(
                role_catalog=catalog,
                runtime_root=root_a,
            )
            service_b = DeerFlowRuntimeAssetsService(
                role_catalog=catalog,
                runtime_root=root_b,
            )

            # 准备配置（使用最小配置）
            from configuration.llm_configuration import LlmConfiguration
            from configuration.llm_model_profile import LlmModelProfile
            from configuration.deerflow_runtime_configuration import (
                DeerFlowRuntimeConfiguration,
            )

            config = LlmConfiguration(
                models=(
                    LlmModelProfile(
                        name="test-model",
                        provider_name="test-provider",
                        model_name="test-model",
                        base_url="https://test.example.com",
                        api_key_env="TEST_API_KEY",
                        api_key="fake-key",
                    ),
                ),
                default_model_name="test-model",
                runtime_configuration=DeerFlowRuntimeConfiguration(
                    tool_search_enabled=False,
                    sandbox_allow_host_bash=False,
                ),
            )

            assets_a = service_a.prepare_assets(config)
            assets_b = service_b.prepare_assets(config)

            # 验证 runtime_root 和 runtime_home 按 runtime_root 独立隔离
            self.assertNotEqual(assets_a.runtime_root, assets_b.runtime_root)
            self.assertNotEqual(assets_a.runtime_home, assets_b.runtime_home)
            # 验证各自落在对应的 runtime_root 下（resolve 为绝对路径比较）
            self.assertEqual(assets_a.runtime_root, root_a.resolve())
            self.assertEqual(assets_b.runtime_root, root_b.resolve())
            # config_path / extensions_config_path 指向同一静态文件（静态化后不再随 runtime_root 变化）
            self.assertEqual(assets_a.config_path, assets_b.config_path)
            self.assertNotEqual(assets_a.config_path, assets_b.runtime_home)


class TestInvocationRunnerIsolation(unittest.TestCase):
    """验证 DeerFlowInvocationRunner 的 os.environ 隔离。

    注意：os.environ 快照恢复只能"缩小污染窗口"，不能保证真正的并发安全。
    - 单进程串行调用：无问题
    - 单进程多线程：os.environ 不是线程安全的，仍存在竞写风险
    - 单进程 async 协程：contextvars 可以保护本 runner 写入的快照不影响其他协程
    - 多进程：需子进程隔离才能彻底避免环境变量冲突

    当前实现适用于"单进程串行请求"场景（CLI + API 单 worker）。
    """

    def test_run_with_isolation_restores_environ(self):
        """验证 run_with_isolation 执行后 os.environ 被完全恢复。

        测试目标：
        1. 调用期间注入的环境变量对被调函数可见
        2. 调用期间临时修改的环境变量不会泄露到外部
        3. 调用结束后原始 os.environ 被完全恢复
        """
        import os

        # 保存原始环境
        original_env = dict(os.environ)
        # 确保测试前不存在此变量
        os.environ.pop("TEST_ISOLATION_VAR", None)
        os.environ.pop("DEER_FLOW_CONFIG_PATH", None)

        # 构造真实的 DeerFlowInvocationRunner（只需 mock client_factory）
        runner = DeerFlowInvocationRunner(
            client_factory=MagicMock(),
        )

        # 构造 fake assets
        fake_assets = MagicMock()
        fake_assets.environment_variables = {
            "TEST_ISOLATION_VAR": "injected_from_assets"
        }
        fake_assets.config_path = Path("/fake/config.yaml")
        fake_assets.extensions_config_path = Path("/fake/ext.json")
        fake_assets.runtime_home = Path("/fake/home")

        fake_client = MagicMock()
        call_result: dict = {}

        def capture_env_and_modify(client):
            """在调用期间捕获环境变量并尝试修改。"""
            # 验证注入的变量在调用期间可见
            call_result["saw_injected"] = os.environ.get("TEST_ISOLATION_VAR")
            # 验证原始变量在调用期间不存在
            call_result["original_missing"] = "ORIGINAL_VAR" not in os.environ
            # 在调用期间修改环境变量
            os.environ["TEST_ISOLATION_VAR"] = "modified_inside"
            call_result["modified_value"] = os.environ.get("TEST_ISOLATION_VAR")

        try:
            # 第一次调用前设置测试变量（模拟其他请求设置的变量）
            os.environ["TEST_ISOLATION_VAR"] = "from_other_request"
            os.environ["ORIGINAL_VAR"] = "should_be_preserved"

            # 调用 run_with_isolation
            result = runner.run_with_isolation(
                fake_assets, fake_client, capture_env_and_modify
            )

            # 验证调用期间的行为
            self.assertEqual(
                call_result["saw_injected"],
                "injected_from_assets",
                "调用期间应看到注入的变量",
            )
            self.assertEqual(
                call_result["modified_value"],
                "modified_inside",
                "调用期间可以修改环境变量",
            )

            # 验证调用结束后 os.environ 被完全恢复
            self.assertNotEqual(
                os.environ.get("TEST_ISOLATION_VAR"),
                "modified_inside",
                "调用结束后修改不应泄露",
            )
            self.assertEqual(
                os.environ.get("TEST_ISOLATION_VAR"),
                "from_other_request",
                "调用结束后应恢复到调用前的值",
            )
            self.assertEqual(
                os.environ.get("ORIGINAL_VAR"),
                "should_be_preserved",
                "其他环境变量在调用后应保持不变（快照恢复）",
            )

        finally:
            # 清理测试变量
            os.environ.pop("TEST_ISOLATION_VAR", None)
            os.environ.pop("ORIGINAL_VAR", None)
            # 确保恢复到原始状态
            os.environ.clear()
            os.environ.update(original_env)


class TestGlobalInvocationLockSerialization(unittest.TestCase):
    """验证全局锁确保同进程内两个线程的 DeerFlow 调用严格串行。

    这是"进程内串行保护"，不是多进程完全并发安全：
    - 同进程多线程：全局锁确保严格串行，os.environ 不会被并发破坏
    - 跨进程：需子进程隔离才能彻底避免冲突（当前未实现）
    - asyncio 协程：单线程内协程切换时 contextvars 传播由调用方保证
    """

    def test_concurrent_calls_are_serialized_by_global_lock(self):
        """验证两个并发调用不会同时进入临界区。

        场景：
        1. 线程 1 先获取锁，进入临界区，使用 Event 等待
        2. 线程 2 尝试获取锁，被阻塞
        3. 线程 1 完成，释放锁
        4. 线程 2 获取锁，进入临界区

        验证：线程 2 的进入临界区时间点 > 线程 1 的完成时间点，
        证明全局锁产生了实际的串行化效果。
        """
        runner = DeerFlowInvocationRunner(
            client_factory=MagicMock(),
        )
        fake_assets = MagicMock()
        fake_assets.environment_variables = {}
        fake_assets.config_path = Path("/fake/config.yaml")
        fake_assets.extensions_config_path = Path("/fake/ext.json")
        fake_assets.runtime_home = Path("/fake/home")

        fake_client = MagicMock()
        call_sequence = []
        lock = threading.Lock()

        # 事件用于线程间同步
        thread_1_in_critical = threading.Event()
        thread_2_can_proceed = threading.Event()
        thread_1_done = threading.Event()

        def slow_invocation(client):
            """模拟慢速调用，主动阻塞以放大竞态窗口。"""
            with lock:
                call_sequence.append("thread_1_enter")
            # 通知主线程：线程 1 已进入临界区
            thread_1_in_critical.set()
            # 等待主线程允许线程 1 继续（模拟慢速调用）
            thread_2_can_proceed.wait(timeout=2)
            with lock:
                call_sequence.append("thread_1_exit")
            thread_1_done.set()

        def waiting_invocation(client):
            """线程 2 的调用：应该被全局锁阻塞，直到线程 1 完成。"""
            call_sequence.append("thread_2_enter")
            return "thread_2_done"

        # 启动线程 1（先持有锁一段时间）
        t1 = threading.Thread(
            target=lambda: runner.run_with_isolation(
                fake_assets, fake_client, slow_invocation
            )
        )
        t1.start()

        # 等待线程 1 进入临界区
        thread_1_in_critical.wait(timeout=2)
        self.assertIn(
            "thread_1_enter",
            call_sequence,
            "线程 1 应该已进入临界区",
        )

        # 启动线程 2（应该被阻塞在锁上）
        t2 = threading.Thread(
            target=lambda: runner.run_with_isolation(
                fake_assets, fake_client, waiting_invocation
            )
        )
        t2.start()

        # 给一点时间让线程 2 尝试获取锁（但应被阻塞）
        time.sleep(0.1)

        # 验证线程 2 尚未进入临界区（因为线程 1 还持有锁）
        self.assertNotIn(
            "thread_2_enter",
            call_sequence,
            "线程 2 在线程 1 持有锁期间不应进入临界区",
        )

        # 允许线程 1 继续并完成
        thread_2_can_proceed.set()
        thread_1_done.wait(timeout=2)
        t1.join(timeout=2)

        # 验证线程 1 已完成
        self.assertIn(
            "thread_1_exit",
            call_sequence,
            "线程 1 应该已完成",
        )

        # 线程 2 现在应该能获取锁并完成
        t2.join(timeout=2)

        # 验证线程 2 进入了临界区
        self.assertIn(
            "thread_2_enter",
            call_sequence,
            "线程 2 应该已进入临界区",
        )

        # 验证串行顺序：线程 1 完全完成后线程 2 才进入
        idx_1_exit = call_sequence.index("thread_1_exit")
        idx_2_enter = call_sequence.index("thread_2_enter")
        self.assertLess(
            idx_1_exit,
            idx_2_enter,
            f"线程 1 退出（索引 {idx_1_exit}）应先于线程 2 进入（索引 {idx_2_enter}）",
        )

        # 验证最终顺序
        self.assertEqual(
            call_sequence,
            ["thread_1_enter", "thread_1_exit", "thread_2_enter"],
        )


if __name__ == "__main__":
    unittest.main()
