"""最终回复摘要测试。"""

import unittest

from department.workbench.final_reply_summary_builder import FinalReplySummaryBuilder


class FinalReplySummaryBuilderTest(unittest.TestCase):
    """验证最终回复压缩逻辑。"""

    def test_prefers_first_complete_sentence(self):
        """首句足够表达结论时优先使用首句。"""
        builder = FinalReplySummaryBuilder()

        summary = builder.build("凭证已记录，凭证号为 1。下一步可以复核这张凭证。")

        self.assertEqual(summary, "凭证已记录，凭证号为 1。")

    def test_truncates_long_reply(self):
        """过长回复被截断，避免协作摘要污染展示。"""
        builder = FinalReplySummaryBuilder()

        summary = builder.build("凭证处理结果：" + "明细很多" * 80)

        self.assertLessEqual(len(summary), 180)
        self.assertTrue(summary.endswith("…"))


if __name__ == "__main__":
    unittest.main()
