"""协作步骤类型枚举。"""

from enum import Enum


class CollaborationStepType(Enum):
    """协作步骤类型枚举。

    描述步骤的本质，帮助用户在协作摘要中理解系统做了什么。
    """

    #: 调用工具（generate_fiscal_task_prompt 等业务工具）
    TOOL_CALL = "tool_call"
    #: 工具执行结果
    TOOL_RESULT = "tool_result"
    #: 委托 DeerFlow task/subagent
    TASK_CALL = "task_call"
    #: 最终结论（DeerFlow 多 agent 协作的最终回复）
    FINAL_REPLY = "final_reply"