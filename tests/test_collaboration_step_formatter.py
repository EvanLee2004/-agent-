"""协作步骤格式化测试。"""

import unittest

from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_formatter import CollaborationStepFormatter
from department.workbench.collaboration_step_type import CollaborationStepType


class CollaborationStepFormatterTest(unittest.TestCase):
    """验证 CLI 协作摘要展示。"""

    def test_formats_accounting_tool_step(self):
        """会计工具步骤应展示工具名和目标。"""
        formatter = CollaborationStepFormatter()
        text = formatter.format(
            [
                CollaborationStep(
                    goal="记录一笔收入凭证",
                    step_type=CollaborationStepType.TOOL_CALL,
                    tool_name="record_voucher",
                    summary="记录凭证",
                )
            ]
        )

        self.assertIn("协作摘要", text)
        self.assertIn("调用工具 - 记录凭证", text)
        self.assertIn("工具：record_voucher", text)
        self.assertIn("目标：记录一笔收入凭证", text)

    def test_truncates_final_reply_summary(self):
        """最终回复过长时只展示压缩摘要。"""
        formatter = CollaborationStepFormatter()
        long_text = "这是一个很长的最终回复。" * 20

        text = formatter.format(
            [
                CollaborationStep(
                    goal="查询凭证",
                    step_type=CollaborationStepType.FINAL_REPLY,
                    tool_name="",
                    summary=long_text,
                )
            ]
        )

        self.assertIn("系统结论", text)
        self.assertIn("…", text)
        self.assertLess(len(text), len(long_text) + 40)


if __name__ == "__main__":
    unittest.main()
