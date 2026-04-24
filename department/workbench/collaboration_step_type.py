"""协作步骤类型枚举。"""

from enum import Enum


class CollaborationStepType(Enum):
    """协作步骤类型枚举。

    描述步骤的本质，帮助用户在协作摘要中理解系统做了什么。
    """

    #: 调用工具（record_voucher、query_vouchers 等会计工具）
    TOOL_CALL = "tool_call"
    #: 工具执行结果
    TOOL_RESULT = "tool_result"
    #: 执行会计部门固定任务步骤
    TASK_CALL = "task_call"
    #: 最终结论（crewAI 会计部门的最终回复）
    FINAL_REPLY = "final_reply"
