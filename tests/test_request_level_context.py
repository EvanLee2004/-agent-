"""请求级上下文隔离与运行时资产隔离测试。

验证 Phase 1 引入的两个核心隔离机制：
1. FinanceDepartmentToolContextRegistry.open_context_scope() 实现请求级上下文生命周期
2. 独立 runtime_root 导致 DeerFlow 运行时资产隔离
"""

import tempfile
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
from department.finance_department_agent_assets_service import (
    FinanceDepartmentAgentAssetsService,
)
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
            agent_assets = FinanceDepartmentAgentAssetsService(catalog)

            service_a = DeerFlowRuntimeAssetsService(
                department_agent_assets_service=agent_assets,
                runtime_root=root_a,
            )
            service_b = DeerFlowRuntimeAssetsService(
                department_agent_assets_service=agent_assets,
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

            # 验证两个 runtime_root 的资产路径完全不同
            self.assertNotEqual(assets_a.runtime_root, assets_b.runtime_root)
            self.assertNotEqual(assets_a.config_path, assets_b.config_path)
            self.assertNotEqual(assets_a.runtime_home, assets_b.runtime_home)
            # 验证各自落在对应的 runtime_root 下（resolve 为绝对路径比较）
            self.assertEqual(assets_a.runtime_root, root_a.resolve())
            self.assertEqual(assets_b.runtime_root, root_b.resolve())


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
        mock_client_factory = MagicMock()
        mock_assets_service = MagicMock()
        mock_config = MagicMock()

        runner = DeerFlowInvocationRunner(
            client_factory=mock_client_factory,
            runtime_assets_service=mock_assets_service,
            configuration=mock_config,
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


if __name__ == "__main__":
    unittest.main()
