"""协作步骤模型。"""

from dataclasses import dataclass

from department.workbench.collaboration_step_type import CollaborationStepType


@dataclass(frozen=True)
class CollaborationStep:
    """描述用户会话中一个逻辑协作步骤。

    阶段 4 重定义：协作步骤来自 DeerFlow stream 事件，而非最终 reply_text 的二次压缩。
    每个步骤对应一个可识别的执行动作（工具调用、任务委托、最终结论）。

    Attributes:
        goal: 本步骤对应的原始用户目标或子目标。
        step_type: 步骤类型，区分工具调用、任务委托、最终结论。
        tool_name: 被调用的工具名称（TOOL_CALL/TASK_CALL 时有值，否则为空字符串）。
        summary: 对用户可见的简短结论，简洁描述本步骤的输出。
            不包含原始长文本 thinking。
    """

    goal: str
    step_type: CollaborationStepType
    tool_name: str
    summary: str
