"""CLI 路由测试。"""

import unittest
from io import StringIO
from unittest.mock import patch

from app.cli_router import CliRouter


class FakeConfigurationService:
    """测试用配置服务。"""


class CliRouterTest(unittest.TestCase):
    """验证 CLI 对外文案已收敛到当前财务部门边界。"""

    def test_banner_mentions_supported_finance_scope(self):
        """启动横幅只展示当前支持的会计与银行流水能力。"""
        router = CliRouter(FakeConfigurationService())

        with patch("sys.stdout", new_callable=StringIO) as stdout:
            router._print_banner()

        text = stdout.getvalue()
        self.assertIn("智能财务部门已启动", text)
        self.assertIn("凭证", text)
        self.assertIn("科目查询", text)
        self.assertIn("银行流水", text)
        self.assertNotIn("税", text)


if __name__ == "__main__":
    unittest.main()
