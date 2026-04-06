"""DeerFlow 模块 smoke test.

验证所有 DeerFlow 模块可以正常导入（现从 submodule editable install 加载），不涉及业务逻辑。
"""

import unittest
from unittest.mock import MagicMock, patch


class TestVendorImports(unittest.TestCase):
    """验证所有 DeerFlow 模块可导入（来自 vendor/deer-flow submodule）."""

    def test_runtime_runs_schemas(self):
        from deerflow.runtime.runs.schemas import DisconnectMode, RunStatus

        self.assertEqual(RunStatus.pending, "pending")
        self.assertEqual(DisconnectMode.cancel, "cancel")

    def test_runtime_runs_manager(self):
        from deerflow.runtime.runs.manager import ConflictError, RunManager, UnsupportedStrategyError

        manager = RunManager()
        self.assertIsInstance(manager, RunManager)

    def test_runtime_runs_worker(self):
        # worker.py 主要为 async 函数，无状态可直接导入验证
        from deerflow.runtime.runs import worker

        self.assertTrue(hasattr(worker, "run_agent"))

    def test_runtime_stream_bridge_base(self):
        from deerflow.runtime.stream_bridge.base import (
            END_SENTINEL,
            HEARTBEAT_SENTINEL,
            StreamBridge,
            StreamEvent,
        )

        self.assertTrue(issubclass(StreamBridge, __import__("abc").ABC))
        self.assertIsInstance(StreamEvent("1", "metadata", {}), StreamEvent)

    def test_runtime_stream_bridge_memory(self):
        from deerflow.runtime.stream_bridge.memory import MemoryStreamBridge

        bridge = MemoryStreamBridge()
        self.assertIsInstance(bridge, MemoryStreamBridge)

    def test_runtime_serialization(self):
        from deerflow.runtime.serialization import serialize, serialize_lc_object

        result = serialize_lc_object({"key": "value"})
        self.assertEqual(result, {"key": "value"})

        result = serialize({"a": 1}, mode="values")
        self.assertEqual(result, {"a": 1})

    def test_sandbox_base(self):
        from deerflow.sandbox.sandbox import Sandbox

        self.assertTrue(hasattr(Sandbox, "execute_command"))

    def test_sandbox_exceptions(self):
        from deerflow.sandbox.exceptions import (
            SandboxCommandError,
            SandboxError,
            SandboxFileError,
            SandboxNotFoundError,
            SandboxPermissionError,
            SandboxRuntimeError,
        )

        exc = SandboxError("test", {"detail": "value"})
        self.assertEqual(exc.message, "test")
        self.assertEqual(exc.details, {"detail": "value"})

        not_found = SandboxNotFoundError(sandbox_id="abc")
        self.assertEqual(not_found.sandbox_id, "abc")

    def test_sandbox_security(self):
        from deerflow.sandbox.security import (
            LOCAL_BASH_SUBAGENT_DISABLED_MESSAGE,
            LOCAL_HOST_BASH_DISABLED_MESSAGE,
            is_host_bash_allowed,
            uses_local_sandbox_provider,
        )

        self.assertIsInstance(LOCAL_HOST_BASH_DISABLED_MESSAGE, str)

    def test_sandbox_search(self):
        from deerflow.sandbox.search import (
            GrepMatch,
            find_glob_matches,
            find_grep_matches,
            should_ignore_name,
            should_ignore_path,
        )

        self.assertTrue(should_ignore_name(".git"))
        self.assertFalse(should_ignore_name("main.py"))
        self.assertIsInstance(GrepMatch(path="a.py", line_number=1, line="hello"), GrepMatch)

    def test_sandbox_local(self):
        from deerflow.sandbox.local.local_sandbox import LocalSandbox, PathMapping

        mapping = PathMapping(container_path="/mnt/test", local_path="/local/test", read_only=True)
        self.assertEqual(mapping.container_path, "/mnt/test")
        self.assertTrue(mapping.read_only)

    def test_sandbox_local_provider(self):
        from deerflow.sandbox.local.local_sandbox_provider import LocalSandboxProvider

        # LocalSandboxProvider.__init__ catches exceptions from config loading,
        # so it can be instantiated even without a valid config file.
        provider = LocalSandboxProvider()
        self.assertIsInstance(provider, LocalSandboxProvider)

    def test_sandbox_list_dir(self):
        from deerflow.sandbox.local.list_dir import list_dir

        result = list_dir("/tmp", max_depth=1)
        self.assertIsInstance(result, list)

    def test_aio_sandbox_info(self):
        from deerflow.community.aio_sandbox.sandbox_info import SandboxInfo

        info = SandboxInfo(sandbox_id="abc", sandbox_url="http://localhost:8080")
        self.assertEqual(info.sandbox_id, "abc")
        self.assertEqual(info.sandbox_url, "http://localhost:8080")

        d = info.to_dict()
        self.assertEqual(d["sandbox_id"], "abc")

        restored = SandboxInfo.from_dict(d)
        self.assertEqual(restored.sandbox_id, "abc")

    def test_aio_sandbox_backend(self):
        from deerflow.community.aio_sandbox.backend import SandboxBackend, wait_for_sandbox_ready

        self.assertTrue(hasattr(SandboxBackend, "create"))
        self.assertTrue(callable(wait_for_sandbox_ready))

    def test_config_paths(self):
        from deerflow.config.paths import Paths

        # Paths 需要 DEER_FLOW_HOME 或有效 base_dir，测试其可实例化
        with patch("deerflow.config.paths.Path") as mock_path:
            mock_path.cwd.return_value.name = "backend"
            paths = Paths()
            self.assertIsInstance(paths, Paths)

    def test_reflection_resolvers(self):
        from deerflow.reflection.resolvers import resolve_class, resolve_variable

        # 验证 resolve_variable 对标准库可用（不校验 expected_type）
        result = resolve_variable("os:path")
        import os.path
        self.assertEqual(result, os.path)


class TestVendorAsyncSmoke(unittest.IsolatedAsyncioTestCase):
    """异步 smoke test."""

    async def test_memory_stream_bridge_publish_subscribe(self):
        from deerflow.runtime.stream_bridge.memory import MemoryStreamBridge

        bridge = MemoryStreamBridge()
        run_id = "test-run"

        await bridge.publish(run_id, "metadata", {"run_id": run_id})
        await bridge.publish_end(run_id)

        events = []
        async for event in bridge.subscribe(run_id):
            events.append(event)
            if hasattr(event, "event") and event.event == "__end__":
                break

        self.assertGreater(len(events), 0)
        # 验证 END sentinel 到达
        self.assertTrue(any(
            hasattr(e, "event") and e.event == "__end__" for e in events
        ))

    async def test_run_manager_create_and_get(self):
        from deerflow.runtime.runs.manager import RunManager
        from deerflow.runtime.runs.schemas import RunStatus

        manager = RunManager()
        record = await manager.create(thread_id="t1")

        self.assertIsNotNone(record.run_id)
        self.assertEqual(record.thread_id, "t1")
        self.assertEqual(record.status, RunStatus.pending)

        retrieved = manager.get(record.run_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.run_id, record.run_id)


if __name__ == "__main__":
    unittest.main()
