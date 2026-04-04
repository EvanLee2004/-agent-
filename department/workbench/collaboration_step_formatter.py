"""协作步骤格式化器。"""

from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_type import CollaborationStepType


STEP_SUMMARY_MAX_CHARS = 120


def _compress_summary_text(text: str) -> str:
    """压缩摘要文本。

    CLI 需要向用户展示"系统做了哪些处理"，但不应该把完整最终回复在协作区域
    再重复打印一遍。这里把多行文本折叠并截断，是为了保留协作透明度，同时控制
    终端噪音，避免让协作摘要反过来破坏主回复可读性。
    """
    normalized_text = " ".join(text.split())
    if len(normalized_text) <= STEP_SUMMARY_MAX_CHARS:
        return normalized_text
    return normalized_text[: STEP_SUMMARY_MAX_CHARS - 1] + "…"


# 步骤类型到中文前缀的映射
_STEP_TYPE_PREFIX = {
    CollaborationStepType.TOOL_CALL: "调用工具",
    CollaborationStepType.TASK_CALL: "委托任务",
    CollaborationStepType.TOOL_RESULT: "工具结果",
    CollaborationStepType.FINAL_REPLY: "系统结论",
}


class CollaborationStepFormatter:
    """把协作步骤渲染为 CLI 可读文本。"""

    def format(self, steps: list[CollaborationStep]) -> str:
        """格式化协作步骤。

        阶段 4 重定义：不再展示"角色调用角色"的递归结构，而是展示 DeerFlow
        stream 事件驱动的真实执行过程（工具调用、任务委托、最终结论）。

        Args:
            steps: 当前回合协作步骤列表。

        Returns:
            适合 CLI 打印的多行文本；没有步骤时返回空字符串。
        """
        if not steps:
            return ""
        lines = ["协作摘要："]
        for i, step in enumerate(steps, start=1):
            type_prefix = _STEP_TYPE_PREFIX.get(step.step_type, "处理")
            # 对于 TOOL_CALL/TASK_CALL，summary 已经是动作描述，不再重复截断
            if step.step_type in (CollaborationStepType.TOOL_CALL, CollaborationStepType.TASK_CALL):
                summary_text = step.summary
            else:
                summary_text = _compress_summary_text(step.summary)
            lines.append(f"  步骤 {i}：{type_prefix} - {summary_text}")
            if step.tool_name and step.step_type in (CollaborationStepType.TOOL_CALL, CollaborationStepType.TASK_CALL, CollaborationStepType.TOOL_RESULT):
                lines.append(f"  工具：{step.tool_name}")
            lines.append(f"  目标：{step.goal}")
        return "\n".join(lines)
