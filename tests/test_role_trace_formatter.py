"""角色轨迹格式化测试。"""

import unittest

from department.role_trace import RoleTrace
from department.role_trace_formatter import RoleTraceFormatter


class RoleTraceFormatterTest(unittest.TestCase):
    """验证角色轨迹输出不会污染终端主回复。"""

    def test_formatter_compresses_multiline_summary(self):
        """验证轨迹格式化会压缩多行长摘要。"""
        formatter = RoleTraceFormatter()
        trace_text = formatter.format(
            [
                RoleTrace(
                    role_name="finance-coordinator",
                    display_name="CoordinatorAgent",
                    requested_by=None,
                    goal="你是谁",
                    thinking_summary=(
                        "我是智能财务部门的协调角色。\n"
                        "我会负责理解您的目标、协调其他角色、汇总最终结果。"
                        "如果需要外部政策、税务或账务事实，我会先请求专业角色提供证据。"
                    ),
                    depth=0,
                )
            ]
        )
        self.assertIn("协作过程：", trace_text)
        self.assertIn("思考摘要：我是智能财务部门的协调角色。", trace_text)
        self.assertNotIn("\n我会负责理解您的目标", trace_text)

