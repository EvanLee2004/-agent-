"""API 请求与响应模型。

使用 Pydantic 定义 API 层的数据传输对象，确保 API 边界清晰、
输入验证自动化、与业务模型分离。
"""

from pydantic import BaseModel, Field


class ConversationReplyRequest(BaseModel):
    """POST /api/conversations/{thread_id}/reply 请求体。

    thread_id 通过路径参数传入，不在 body 中重复。
    """

    user_input: str = Field(..., min_length=1, description="用户输入文本")


class CollaborationStepResponse(BaseModel):
    """协作步骤响应。"""

    goal: str
    step_type: str
    tool_name: str
    summary: str


class ConversationReplyResponse(BaseModel):
    """POST /api/conversations/{thread_id}/reply 响应体。"""

    thread_id: str
    reply_text: str
    collaboration_steps: list[CollaborationStepResponse]


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
