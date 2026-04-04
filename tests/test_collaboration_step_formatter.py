"""协作步骤格式化测试。"""

import unittest

from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_type import CollaborationStepType
from department.workbench.collaboration_step_formatter import CollaborationStepFormatter


class CollaborationStepFormatterTest(unittest.TestCase):
    """验证协作步骤格式化输出简洁、不污染主回复。"""

    def test_format_returns_empty_string_for_empty_list(self):
        """空步骤列表返回空字符串。"""
        formatter = CollaborationStepFormatter()
        self.assertEqual(formatter.format([]), "")

    def test_format_single_tool_call_step(self):
        """验证工具调用步骤格式化输出。"""
        formatter = CollaborationStepFormatter()
        step_text = formatter.format(
            [
                CollaborationStep(
                    goal="生成税务 prompt",
                    step_type=CollaborationStepType.TOOL_CALL,
                    tool_name="generate_fiscal_task_prompt",
                    summary="生成财务任务 prompt",
                )
            ]
        )
        lines = step_text.split("\n")
        self.assertIn("协作摘要：", lines[0])
        self.assertIn("步骤 1：调用工具 - 生成财务任务 prompt", lines[1])
        self.assertIn("工具：generate_fiscal_task_prompt", lines[2])
        self.assertIn("目标：生成税务 prompt", lines[3])

    def test_format_single_task_call_step(self):
        """验证任务委托步骤格式化输出。"""
        formatter = CollaborationStepFormatter()
        step_text = formatter.format(
            [
                CollaborationStep(
                    goal="计算企业所得税",
                    step_type=CollaborationStepType.TASK_CALL,
                    tool_name="task",
                    summary="委托子代理任务",
                )
            ]
        )
        lines = step_text.split("\n")
        self.assertIn("协作摘要：", lines[0])
        self.assertIn("步骤 1：委托任务 - 委托子代理任务", lines[1])
        self.assertIn("工具：task", lines[2])
        self.assertIn("目标：计算企业所得税", lines[3])

    def test_format_final_reply_step(self):
        """验证最终结论步骤格式化输出。"""
        formatter = CollaborationStepFormatter()
        step_text = formatter.format(
            [
                CollaborationStep(
                    goal="你好",
                    step_type=CollaborationStepType.FINAL_REPLY,
                    tool_name="",
                    summary="我是智能财务部门的协调角色。我会负责理解您的目标。",
                )
            ]
        )
        lines = step_text.split("\n")
        self.assertIn("协作摘要：", lines[0])
        self.assertIn("步骤 1：系统结论 - 我是智能财务部门的协调角色。我会负责理解您的目标。", lines[1])
        self.assertIn("目标：你好", lines[2])

    def test_format_tool_result_step(self):
        """验证工具结果步骤格式化输出（不暴露原始 JSON）。"""
        formatter = CollaborationStepFormatter()
        step_text = formatter.format(
            [
                CollaborationStep(
                    goal="记录收款",
                    step_type=CollaborationStepType.TOOL_RESULT,
                    tool_name="generate_fiscal_task_prompt",
                    summary="财务任务 prompt 已生成",
                )
            ]
        )
        lines = step_text.split("\n")
        self.assertIn("协作摘要：", lines[0])
        # 摘要已是标准化中文，不应包含原始 JSON
        self.assertIn("步骤 1：工具结果 - 财务任务 prompt 已生成", lines[1])
        self.assertIn("工具：generate_fiscal_task_prompt", lines[2])
        self.assertIn("目标：记录收款", lines[3])
        # 确保没有暴露原始 JSON
        self.assertNotIn('{"prompt"', step_text)
        self.assertNotIn('"status"', step_text)

    def test_format_full_collaboration_sequence(self):
        """验证完整协作序列格式化输出（TOOL_RESULT 展示为标准化结论）。"""
        formatter = CollaborationStepFormatter()
        step_text = formatter.format(
            [
                CollaborationStep(
                    goal="记录收款",
                    step_type=CollaborationStepType.TOOL_CALL,
                    tool_name="generate_fiscal_task_prompt",
                    summary="生成财务任务 prompt",
                ),
                CollaborationStep(
                    goal="记录收款",
                    step_type=CollaborationStepType.TOOL_RESULT,
                    tool_name="generate_fiscal_task_prompt",
                    summary="财务任务 prompt 已生成",
                ),
                CollaborationStep(
                    goal="记录收款",
                    step_type=CollaborationStepType.TASK_CALL,
                    tool_name="task",
                    summary="委托子代理任务",
                ),
                CollaborationStep(
                    goal="记录收款",
                    step_type=CollaborationStepType.TOOL_RESULT,
                    tool_name="task",
                    summary="子代理任务已返回结果",
                ),
                CollaborationStep(
                    goal="记录收款",
                    step_type=CollaborationStepType.FINAL_REPLY,
                    tool_name="",
                    summary="已为你记录收款凭证。",
                ),
            ]
        )
        # 输出结构（每个有 tool_name 的步骤 3 行，FINAL_REPLY 无 tool 行共 2 行）：
        # 协作摘要：
        # 步骤 1：调用工具 - 生成财务任务 prompt  (line 1)
        # 工具：generate_fiscal_task_prompt              (line 2)
        # 目标：记录收款                                   (line 3)
        # 步骤 2：工具结果 - 财务任务 prompt 已生成    (line 4)
        # 工具：generate_fiscal_task_prompt              (line 5)
        # 目标：记录收款                                   (line 6)
        # 步骤 3：委托任务 - 委托子代理任务               (line 7)
        # 工具：task                                       (line 8)
        # 目标：记录收款                                   (line 9)
        # 步骤 4：工具结果 - 子代理任务已返回结果      (line 10)
        # 工具：task                                       (line 11)
        # 目标：记录收款                                   (line 12)
        # 步骤 5：系统结论 - 已为你记录收款凭证。      (line 13)
        # 目标：记录收款                                   (line 14)
        lines = step_text.split("\n")
        self.assertIn("协作摘要：", lines[0])
        self.assertIn("步骤 1：调用工具 - 生成财务任务 prompt", lines[1])
        self.assertIn("工具：generate_fiscal_task_prompt", lines[2])
        self.assertIn("步骤 2：工具结果 - 财务任务 prompt 已生成", lines[4])
        self.assertIn("步骤 3：委托任务 - 委托子代理任务", lines[7])
        self.assertIn("步骤 4：工具结果 - 子代理任务已返回结果", lines[10])
        self.assertIn("步骤 5：系统结论 - 已为你记录收款凭证。", lines[13])
        # 确保没有暴露原始 JSON
        self.assertNotIn('{"prompt"', step_text)
        self.assertNotIn('{"status"', step_text)
