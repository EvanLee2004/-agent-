"""角色摘要构造器测试。"""

import unittest

from department.workbench.role_trace_summary_builder import RoleTraceSummaryBuilder


class RoleTraceSummaryBuilderTest(unittest.TestCase):
    """验证角色摘要构造逻辑。"""

    def test_build_prefers_first_sentence_for_long_reply(self):
        """验证长回复优先提取首句，避免把完整答复塞进轨迹。"""
        builder = RoleTraceSummaryBuilder()

        summary = builder.build(
            "我们是智能财务部门，将根据您的需求协调记账、审核、税前准备和政策研究。"
            "\n\n如果需要，我还可以继续分派其他角色协作完成具体任务。"
        )

        self.assertEqual(
            summary,
            "我们是智能财务部门，将根据您的需求协调记账、审核、税前准备和政策研究。",
        )
