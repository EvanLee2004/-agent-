"""API 请求与响应模型。

使用 Pydantic 定义 API 层的数据传输对象，确保 API 边界清晰、
输入验证自动化、与业务模型分离。
"""

from pydantic import BaseModel, Field


class ConversationReplyRequest(BaseModel):
    """POST /api/accounting/{thread_id}/reply 请求体。

    thread_id 通过路径参数传入，不在 body 中重复。
    """

    user_input: str = Field(..., min_length=1, description="用户输入文本")


class CollaborationStepResponse(BaseModel):
    """协作步骤响应。"""

    goal: str
    step_type: str
    tool_name: str
    summary: str


class AccountingReplyResponse(BaseModel):
    """POST /api/accounting/{thread_id}/reply 响应体。

    API 响应面向“会计核算结果”而不是通用聊天消息。reply_text 保留给用户的
    完整自然语言回复；steps 是可展示的协作过程；voucher_ids 和 audit_summary
    是会计业务上最常被上游系统消费的结构化字段；errors 预留给后续批量处理或
    局部失败场景，当前正常路径为空列表。
    """

    reply_text: str
    steps: list[CollaborationStepResponse]
    voucher_ids: list[int] = Field(default_factory=list)
    audit_summary: str | None = None
    errors: list[str] = Field(default_factory=list)


class TurnHistoryItem(BaseModel):
    """单轮对话历史项。"""

    thread_id: str
    original_user_input: str
    reply_text: str
    collaboration_steps: list[CollaborationStepResponse]


class ExecutionEventResponse(BaseModel):
    """带回合归属的执行事件响应。"""

    event_type: str
    tool_name: str
    summary: str
    turn_index: int
    event_sequence: int


class HealthResponse(BaseModel):
    """GET /health 响应体。"""

    status: str = "ok"
    version: str = "1.0.0"
