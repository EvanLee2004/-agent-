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


class ToolResultResponse(BaseModel):
    """结构化工具结果响应。"""

    tool_name: str
    success: bool
    payload: dict
    error_message: str | None = None
    voucher_ids: list[int] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """统一 API 错误响应。"""

    error_code: str
    message: str
    request_id: str
    details: dict = Field(default_factory=dict)


class AccountingReplyResponse(BaseModel):
    """POST /api/accounting/{thread_id}/reply 响应体。

    API 响应面向“财务部门处理结果”而不是通用聊天消息。reply_text 保留给用户的
    完整自然语言回复；steps 是可展示的协作过程；voucher_ids 和 audit_summary
    是会计业务上最常被上游系统消费的结构化字段；errors 预留给后续批量处理或
    局部失败场景，当前正常路径为空列表。
    """

    reply_text: str
    steps: list[CollaborationStepResponse]
    tool_results: list[ToolResultResponse] = Field(default_factory=list)
    voucher_ids: list[int] = Field(default_factory=list)
    audit_summary: str | None = None
    context_refs: list[str] = Field(default_factory=list)
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


class PeriodResponse(BaseModel):
    """会计期间响应。"""

    period_name: str
    start_date: str
    end_date: str
    status: str
    closed_at: str | None = None


class VoucherActionResponse(BaseModel):
    """凭证生命周期动作响应。"""

    voucher_id: int
    voucher_number: str
    period_name: str
    voucher_date: str
    summary: str
    status: str
    source_voucher_id: int | None = None
    lifecycle_action: str
    posted_at: str | None = None
    voided_at: str | None = None


class ReverseVoucherRequest(BaseModel):
    """凭证红冲请求。"""

    reversal_date: str | None = Field(default=None, description="红冲日期 YYYY-MM-DD")


class CorrectVoucherRequest(BaseModel):
    """凭证更正请求。"""

    replacement_voucher: dict
    reversal_date: str | None = Field(default=None, description="红冲日期 YYYY-MM-DD")


class CorrectVoucherResponse(BaseModel):
    """凭证更正响应。"""

    reversal_voucher_id: int
    replacement_voucher_id: int


class AccountBalanceResponse(BaseModel):
    """科目余额响应。"""

    subject_code: str
    subject_name: str
    normal_balance: str
    debit_total: float
    credit_total: float
    balance_direction: str
    balance_amount: float


class LedgerEntryResponse(BaseModel):
    """总账/明细账响应。"""

    voucher_id: int
    voucher_number: str
    voucher_date: str
    period_name: str
    subject_code: str
    subject_name: str
    debit_amount: float
    credit_amount: float
    summary: str
    description: str


class TrialBalanceResponse(BaseModel):
    """试算平衡响应。"""

    period_name: str | None = None
    debit_total: float
    credit_total: float
    difference: float
    balanced: bool
    rows: list[AccountBalanceResponse] = Field(default_factory=list)


class ReconcileBankTransactionRequest(BaseModel):
    """银行流水对账请求。"""

    linked_voucher_id: int | None = None


class BankTransactionResponse(BaseModel):
    """银行流水响应。"""

    transaction_id: int
    transaction_date: str
    direction: str
    amount: float
    account_name: str
    counterparty: str
    summary: str
    status: str
    linked_voucher_id: int | None = None


class VoucherSuggestionResponse(BaseModel):
    """银行流水入账建议响应。"""

    transaction_id: int
    suggested_voucher: dict


class IntegrityCheckResponse(BaseModel):
    """账簿完整性检查响应。"""

    ok: bool
    issues: list[str] = Field(default_factory=list)
