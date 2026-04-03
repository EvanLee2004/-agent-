"""CLI 路由入口测试。"""

import io
import unittest
from contextlib import redirect_stdout

from app.cli_router import CliRouter


class StubConfigurationService:
    """CLI 测试用配置服务替身。"""


class CliRouterTest(unittest.TestCase):
    """验证 CLI 路由入口的用户体验边界。"""

    def test_run_handles_keyboard_interrupt_gracefully(self):
        """验证 Ctrl+C 会安静退出，而不是抛出 Python 栈。"""
        router = CliRouter(StubConfigurationService())

        def raise_keyboard_interrupt() -> None:
            raise KeyboardInterrupt()

        router._run_event_loop = raise_keyboard_interrupt  # type: ignore[method-assign]
        output_buffer = io.StringIO()
        with redirect_stdout(output_buffer):
            router.run()
        self.assertIn("再见！", output_buffer.getvalue())

