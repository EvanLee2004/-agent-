"""crewAI-first 财务部门 API 入口。

FastAPI 应用，提供两类边界：
- 智能对话接口：与 CLI 共用同一条 crewAI 财务部门链路
- 确定性业务接口：期间、凭证生命周期、报表和银行对账直接调用领域服务

依赖注入设计：
- conversation_handler / workbench_service 通过 create_app() 注入
- accounting_service / cashier_service 通过 create_app() 注入
- 生产路径使用 AppServiceFactory 构造完整依赖
- 测试路径可注入 mock 或真实局部服务

端点：
- POST /api/accounting/{thread_id}/reply：处理会计/银行流水请求，返回财务部门响应
- POST /api/accounting/vouchers/{voucher_id}/post|void|reverse|correct：凭证生命周期
- GET /api/accounting/reports/*：账簿报表
- POST /api/accounting/bank-transactions/{transaction_id}/reconcile|unreconcile：银行对账
- GET /api/accounting/{thread_id}/turns：获取线程历史（多回合）
- GET /api/accounting/{thread_id}/collaboration-steps：获取协作步骤历史
- GET /api/accounting/{thread_id}/events：获取内部执行事件
- GET /health：健康检查
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import uuid

from fastapi import FastAPI, HTTPException, Path as FPath, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.models import (
    AccountBalanceResponse,
    AccountingReplyResponse,
    BankTransactionResponse,
    CollaborationStepResponse,
    ConversationReplyRequest,
    CorrectVoucherRequest,
    CorrectVoucherResponse,
    ErrorResponse,
    ExecutionEventResponse,
    HealthResponse,
    IntegrityCheckResponse,
    LedgerEntryResponse,
    PeriodResponse,
    ReconcileBankTransactionRequest,
    ReverseVoucherRequest,
    ToolResultResponse,
    TrialBalanceResponse,
    TurnHistoryItem,
    VoucherActionResponse,
    VoucherSuggestionResponse,
)
from accounting.accounting_error import AccountingError
from accounting.correct_voucher_command import CorrectVoucherCommand
from accounting.record_voucher_command import RecordVoucherCommand
from accounting.reverse_voucher_command import ReverseVoucherCommand
from accounting.voucher_draft import VoucherDraft
from cashier.cashier_error import CashierError
from cashier.reconcile_bank_transaction_command import ReconcileBankTransactionCommand
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse

if TYPE_CHECKING:
    from app.conversation_request_handler import AppConversationHandler
    from accounting.accounting_service import AccountingService
    from cashier.cashier_service import CashierService
    from department.workbench.department_workbench_service import DepartmentWorkbenchService


def create_app(
    conversation_handler: AppConversationHandler | None = None,
    workbench_service: DepartmentWorkbenchService | None = None,
    accounting_service: AccountingService | None = None,
    cashier_service: CashierService | None = None,
    configuration_service=None,
) -> FastAPI:
    """构造 FastAPI 应用实例。

    支持依赖注入：生产环境传入真实实例，测试环境传入 mock 实例。

    Args:
        conversation_handler: API 请求处理器（即 AppConversationHandler）。
            内部持有纯净的 ConversationRouter 和 tool_context，
            在 handle() 中管理请求级作用域并将异常翻译为 HTTP 400/500。
            为 None 时内部自动构造（生产路径）。
        workbench_service: 工作台服务，用于查询接口。
            为 None 时内部自动构造（生产路径）。
        accounting_service: 确定性账务 API 使用的会计服务。
        cashier_service: 确定性银行 API 使用的出纳服务。
        configuration_service: 配置服务（仅在自动构造时使用）。

    Returns:
        配置完成的 FastAPI 应用实例。
    """
    app = FastAPI(
        title="智能财务部门 API",
        description=(
            "crewAI-first 多 Agent 财务部门后端，当前覆盖会计期间、"
            "凭证生命周期、账簿报表、会计科目、银行流水和对账。"
        ),
        version="1.0.0",
    )

    # ========================================================================
    # 依赖注入：优先使用注入的实例，否则自动构造（生产路径）
    # ========================================================================
    if (
        conversation_handler is None
        and accounting_service is None
        and cashier_service is None
    ):
        # 生产路径：从配置服务构造完整链路
        if configuration_service is None:
            from configuration.configuration_service import ConfigurationService
            from configuration.file_configuration_repository import FileConfigurationRepository
            from configuration.provider_catalog import ProviderCatalog

            configuration_service = ConfigurationService(
                FileConfigurationRepository(),
                ProviderCatalog(),
            )
        from app.dependency_container import AppServiceFactory

        llm_configuration = configuration_service.ensure_configuration()
        _api_runtime_root = Path(".runtime") / "api"
        _api_runtime_root.mkdir(parents=True, exist_ok=True)
        factory = AppServiceFactory(
            llm_configuration=llm_configuration,
            runtime_root=_api_runtime_root,
        )
        factory.build_application_bootstrapper().initialize()
        conversation_handler, workbench_service = factory.build_api_dependencies()
        accounting_service = factory.build_accounting_service()
        cashier_service = factory.build_cashier_service()

    # 将依赖存入 app.state，供端点访问
    app.state.conversation_handler = conversation_handler
    app.state.workbench_service = workbench_service
    app.state.accounting_service = accounting_service
    app.state.cashier_service = cashier_service

    @app.exception_handler(AccountingError)
    async def accounting_error_handler(
        request: Request,
        exc: AccountingError,
    ) -> JSONResponse:
        """把会计业务异常转换为统一错误响应。"""
        return _build_error_response(request, "ACCOUNTING_ERROR", str(exc), 400)

    @app.exception_handler(CashierError)
    async def cashier_error_handler(
        request: Request,
        exc: CashierError,
    ) -> JSONResponse:
        """把出纳业务异常转换为统一错误响应。"""
        return _build_error_response(request, "CASHIER_ERROR", str(exc), 400)

    @app.exception_handler(HTTPException)
    async def http_error_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        """把 FastAPI HTTPException 转换为统一错误响应。"""
        return _build_error_response(
            request,
            "HTTP_ERROR",
            str(exc.detail),
            exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """把请求体验证错误转换为统一错误响应。

        FastAPI 默认 422 响应结构偏框架化。生产 API 需要让调用方稳定依赖
        `error_code/message/request_id/details`，所以校验错误也在 API 层收口，
        不把 Pydantic/FastAPI 的响应格式直接作为业务契约。
        """
        return _build_error_response(
            request,
            "VALIDATION_ERROR",
            "请求参数不合法",
            422,
            details={"errors": exc.errors()},
        )

    # ========================================================================
    # 端点定义
    # ========================================================================

    @app.post(
        "/api/accounting/{thread_id}/reply",
        response_model=AccountingReplyResponse,
        summary="处理财务部门回复",
    )
    def reply_conversation(
        thread_id: str = FPath(..., description="线程标识"),
        request: ConversationReplyRequest = ...,
    ) -> AccountingReplyResponse:
        """处理用户输入，返回财务部门协作响应。

        内部流程：ConversationRequest → AppConversationHandler.handle() →
        ConversationRouter.handle() → ConversationService.reply() →
        AccountingDepartmentService → CrewAIAccountingRuntimeRepository → crewAI Crew。

        注意：
        - thread_id 通过路径参数传入，请求体只包含 user_input
        - 内部异常由 AppConversationHandler 翻译为 HTTP 400/500，不暴露第三方运行时细节
        - usage 数据被持久化但不返回给用户
        """
        handler = app.state.conversation_handler
        if handler is None:
            raise HTTPException(status_code=503, detail="会话服务尚未初始化")
        response: ConversationResponse = handler.handle(
            ConversationRequest(
                user_input=request.user_input,
                thread_id=thread_id,
            )
        )
        steps = [
            CollaborationStepResponse(
                goal=step.goal,
                step_type=step.step_type.value,
                tool_name=step.tool_name,
                summary=step.summary,
            )
            for step in response.collaboration_steps
        ]
        tool_results = [
            ToolResultResponse(
                tool_name=result.tool_name,
                success=result.success,
                payload=result.payload,
                error_message=result.error_message,
                voucher_ids=result.voucher_ids,
                context_refs=result.context_refs,
            )
            for result in response.tool_results
        ]
        return AccountingReplyResponse(
            reply_text=response.reply_text,
            steps=steps,
            tool_results=tool_results,
            voucher_ids=_collect_voucher_ids(tool_results),
            audit_summary=_extract_audit_summary(tool_results),
            context_refs=response.context_refs,
            errors=[
                result.error_message
                for result in tool_results
                if not result.success and result.error_message
            ],
        )

    @app.get(
        "/api/accounting/{thread_id}/turns",
        response_model=list[TurnHistoryItem],
        summary="获取线程历史",
    )
    def get_turn_history(
        thread_id: str = FPath(..., description="线程标识"),
    ) -> list[TurnHistoryItem]:
        """获取线程的全部对话历史（多回合）。"""
        workbench_service = app.state.workbench_service
        if workbench_service is None:
            return []
        turns = workbench_service.list_turns_with_steps(thread_id)
        return [
            TurnHistoryItem(
                thread_id=thread_id,
                original_user_input=turn["original_user_input"],
                reply_text=turn["reply_text"],
                collaboration_steps=[
                    CollaborationStepResponse(
                        goal=step.goal,
                        step_type=step.step_type.value,
                        tool_name=step.tool_name,
                        summary=step.summary,
                    )
                    for step in turn.get("collaboration_steps", [])
                ],
            )
            for turn in turns
        ]

    @app.get(
        "/api/accounting/{thread_id}/collaboration-steps",
        response_model=list[CollaborationStepResponse],
        summary="获取协作步骤",
    )
    def get_collaboration_steps(
        thread_id: str = FPath(..., description="线程标识"),
    ) -> list[CollaborationStepResponse]:
        """获取线程全部回合的协作步骤（扁平列表）。"""
        workbench_service = app.state.workbench_service
        if workbench_service is None:
            return []
        steps = workbench_service.list_collaboration_steps(thread_id)
        return [
            CollaborationStepResponse(
                goal=step.goal,
                step_type=step.step_type.value,
                tool_name=step.tool_name,
                summary=step.summary,
            )
            for step in steps
        ]

    @app.get(
        "/api/accounting/{thread_id}/events",
        response_model=list[ExecutionEventResponse],
        summary="获取内部执行事件（含回合归属）",
    )
    def get_events(
        thread_id: str = FPath(..., description="线程标识"),
    ) -> list[ExecutionEventResponse]:
        """获取线程全部回合的内部执行事件（含回合归属上下文）。

        每条事件包含 event_type、tool_name、summary、turn_index（回合序号）、
        event_sequence（事件在该回合内的顺序）。
        不暴露 usage 等敏感遥测数据。
        """
        workbench_service = app.state.workbench_service
        if workbench_service is None:
            return []
        events = workbench_service.list_execution_events_with_context(thread_id)
        return [
            ExecutionEventResponse(
                event_type=evt["event_type"],
                tool_name=evt["tool_name"],
                summary=evt["summary"],
                turn_index=evt["turn_index"],
                event_sequence=evt["event_sequence"],
            )
            for evt in events
        ]

    @app.get(
        "/api/accounting/periods",
        response_model=list[PeriodResponse],
        summary="列出会计期间",
    )
    def list_periods() -> list[PeriodResponse]:
        """列出全部会计期间。"""
        service = _require_accounting_service(app)
        return [_serialize_period(period) for period in service.list_periods()]

    @app.post(
        "/api/accounting/periods/{period_name}/open",
        response_model=PeriodResponse,
        summary="打开会计期间",
    )
    def open_period(
        period_name: str = FPath(..., description="会计期间，格式 YYYYMM"),
    ) -> PeriodResponse:
        """打开或创建会计期间。"""
        service = _require_accounting_service(app)
        return _serialize_period(service.open_period(period_name))

    @app.post(
        "/api/accounting/periods/{period_name}/close",
        response_model=PeriodResponse,
        summary="关闭会计期间",
    )
    def close_period(
        period_name: str = FPath(..., description="会计期间，格式 YYYYMM"),
    ) -> PeriodResponse:
        """关闭会计期间。"""
        service = _require_accounting_service(app)
        return _serialize_period(service.close_period(period_name))

    @app.post(
        "/api/accounting/vouchers/{voucher_id}/post",
        response_model=VoucherActionResponse,
        summary="凭证过账",
    )
    def post_voucher(
        voucher_id: int = FPath(..., description="凭证 ID"),
    ) -> VoucherActionResponse:
        """将凭证过账。"""
        service = _require_accounting_service(app)
        return _serialize_voucher_action(service.post_voucher(voucher_id))

    @app.post(
        "/api/accounting/vouchers/{voucher_id}/void",
        response_model=VoucherActionResponse,
        summary="凭证作废",
    )
    def void_voucher(
        voucher_id: int = FPath(..., description="凭证 ID"),
    ) -> VoucherActionResponse:
        """作废未过账凭证。"""
        service = _require_accounting_service(app)
        return _serialize_voucher_action(service.void_voucher(voucher_id))

    @app.post(
        "/api/accounting/vouchers/{voucher_id}/reverse",
        response_model=VoucherActionResponse,
        summary="凭证红冲",
    )
    def reverse_voucher(
        voucher_id: int = FPath(..., description="凭证 ID"),
        request: ReverseVoucherRequest | None = None,
    ) -> VoucherActionResponse:
        """为已过账凭证创建红冲凭证。"""
        service = _require_accounting_service(app)
        return _serialize_voucher_action(
            service.reverse_voucher(
                ReverseVoucherCommand(
                    voucher_id=voucher_id,
                    reversal_date=request.reversal_date if request else None,
                )
            )
        )

    @app.post(
        "/api/accounting/vouchers/{voucher_id}/correct",
        response_model=CorrectVoucherResponse,
        summary="凭证更正",
    )
    def correct_voucher(
        voucher_id: int = FPath(..., description="凭证 ID"),
        request: CorrectVoucherRequest = ...,
    ) -> CorrectVoucherResponse:
        """通过红冲加新凭证更正已过账凭证。"""
        service = _require_accounting_service(app)
        reversal_id, replacement_id = service.correct_voucher(
            CorrectVoucherCommand(
                voucher_id=voucher_id,
                replacement_command=RecordVoucherCommand(
                    voucher_draft=VoucherDraft.from_dict(request.replacement_voucher)
                ),
                reversal_date=request.reversal_date,
            )
        )
        return CorrectVoucherResponse(
            reversal_voucher_id=reversal_id,
            replacement_voucher_id=replacement_id,
        )

    @app.get(
        "/api/accounting/reports/account-balances",
        response_model=list[AccountBalanceResponse],
        summary="科目余额表",
    )
    def query_account_balances(
        period_name: str | None = Query(default=None, description="会计期间 YYYYMM"),
    ) -> list[AccountBalanceResponse]:
        """查询科目余额表。"""
        service = _require_accounting_service(app)
        return [
            _serialize_account_balance(row)
            for row in service.list_account_balances(period_name)
        ]

    @app.get(
        "/api/accounting/reports/ledger-entries",
        response_model=list[LedgerEntryResponse],
        summary="总账/明细账",
    )
    def query_ledger_entries(
        period_name: str | None = Query(default=None, description="会计期间 YYYYMM"),
        subject_code: str | None = Query(default=None, description="科目编码"),
        limit: int = Query(default=200, ge=1, le=500),
    ) -> list[LedgerEntryResponse]:
        """查询总账或明细账。"""
        service = _require_accounting_service(app)
        return [
            _serialize_ledger_entry(row)
            for row in service.list_ledger_entries(
                period_name=period_name,
                subject_code=subject_code,
                limit=limit,
            )
        ]

    @app.get(
        "/api/accounting/reports/trial-balance",
        response_model=TrialBalanceResponse,
        summary="试算平衡表",
    )
    def query_trial_balance(
        period_name: str | None = Query(default=None, description="会计期间 YYYYMM"),
    ) -> TrialBalanceResponse:
        """查询试算平衡表。"""
        service = _require_accounting_service(app)
        report = service.build_trial_balance(period_name)
        return TrialBalanceResponse(
            period_name=report.period_name,
            debit_total=report.debit_total,
            credit_total=report.credit_total,
            difference=report.difference,
            balanced=report.balanced,
            rows=[_serialize_account_balance(row) for row in report.rows],
        )

    @app.get(
        "/api/accounting/integrity-check",
        response_model=IntegrityCheckResponse,
        summary="账簿完整性检查",
    )
    def integrity_check() -> IntegrityCheckResponse:
        """执行账簿完整性检查。"""
        service = _require_accounting_service(app)
        issues = service.run_integrity_check()
        return IntegrityCheckResponse(ok=not issues, issues=issues)

    @app.post(
        "/api/accounting/bank-transactions/{transaction_id}/reconcile",
        response_model=BankTransactionResponse,
        summary="银行流水对账",
    )
    def reconcile_bank_transaction(
        transaction_id: int = FPath(..., description="银行流水 ID"),
        request: ReconcileBankTransactionRequest | None = None,
    ) -> BankTransactionResponse:
        """把银行流水关联到已过账凭证。"""
        service = _require_cashier_service(app)
        return _serialize_bank_transaction(
            service.reconcile_transaction(
                ReconcileBankTransactionCommand(
                    transaction_id=transaction_id,
                    linked_voucher_id=request.linked_voucher_id if request else None,
                )
            )
        )

    @app.post(
        "/api/accounting/bank-transactions/{transaction_id}/unreconcile",
        response_model=BankTransactionResponse,
        summary="解除银行流水对账",
    )
    def unreconcile_bank_transaction(
        transaction_id: int = FPath(..., description="银行流水 ID"),
    ) -> BankTransactionResponse:
        """解除银行流水对账。"""
        service = _require_cashier_service(app)
        return _serialize_bank_transaction(
            service.unreconcile_transaction(transaction_id)
        )

    @app.get(
        "/api/accounting/bank-transactions/{transaction_id}/voucher-suggestion",
        response_model=VoucherSuggestionResponse,
        summary="银行流水入账建议",
    )
    def suggest_voucher_from_bank_transaction(
        transaction_id: int = FPath(..., description="银行流水 ID"),
    ) -> VoucherSuggestionResponse:
        """根据银行流水生成凭证建议，不写入总账。"""
        service = _require_cashier_service(app)
        return VoucherSuggestionResponse(
            transaction_id=transaction_id,
            suggested_voucher=service.build_voucher_suggestion(transaction_id),
        )

    @app.get("/health", response_model=HealthResponse, summary="健康检查")
    def health() -> HealthResponse:
        """返回服务健康状态。"""
        return HealthResponse(status="ok", version="1.0.0")

    return app


def _collect_voucher_ids(tool_results: list[ToolResultResponse]) -> list[int]:
    """从结构化工具结果汇总凭证 ID。"""
    voucher_ids: set[int] = set()
    for result in tool_results:
        voucher_ids.update(result.voucher_ids)
    return sorted(voucher_ids)


def _extract_audit_summary(
    tool_results: list[ToolResultResponse],
) -> str | None:
    """提取审核摘要。

    审核摘要只能来自 `audit_voucher` 的结构化 payload，不能从最终自然语言回复
    中猜测，避免模型措辞变化影响 API 契约。
    """
    for result in reversed(tool_results):
        if result.tool_name != "audit_voucher" or not result.success:
            continue
        summary = result.payload.get("summary")
        if summary:
            return str(summary)
    return None


def _require_accounting_service(app: FastAPI):
    """读取确定性会计服务依赖。"""
    service = getattr(app.state, "accounting_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="会计服务尚未初始化")
    return service


def _require_cashier_service(app: FastAPI):
    """读取确定性出纳服务依赖。"""
    service = getattr(app.state, "cashier_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="出纳服务尚未初始化")
    return service


def _build_error_response(
    request: Request,
    error_code: str,
    message: str,
    status_code: int,
    details: dict | None = None,
) -> JSONResponse:
    """构造统一错误响应。"""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    payload = ErrorResponse(
        error_code=error_code,
        message=message,
        request_id=request_id,
        details=details or {},
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _serialize_period(period) -> PeriodResponse:
    """序列化会计期间。"""
    return PeriodResponse(
        period_name=period.period_name,
        start_date=period.start_date,
        end_date=period.end_date,
        status=period.status,
        closed_at=period.closed_at,
    )


def _serialize_voucher_action(voucher) -> VoucherActionResponse:
    """序列化凭证生命周期动作结果。"""
    return VoucherActionResponse(
        voucher_id=voucher.voucher_id,
        voucher_number=voucher.voucher_number,
        period_name=voucher.period_name,
        voucher_date=voucher.voucher_date,
        summary=voucher.summary,
        status=voucher.status,
        source_voucher_id=voucher.source_voucher_id,
        lifecycle_action=voucher.lifecycle_action,
        posted_at=voucher.posted_at,
        voided_at=voucher.voided_at,
    )


def _serialize_account_balance(row) -> AccountBalanceResponse:
    """序列化科目余额。"""
    return AccountBalanceResponse(
        subject_code=row.subject_code,
        subject_name=row.subject_name,
        normal_balance=row.normal_balance,
        debit_total=row.debit_total,
        credit_total=row.credit_total,
        balance_direction=row.balance_direction,
        balance_amount=row.balance_amount,
    )


def _serialize_ledger_entry(row) -> LedgerEntryResponse:
    """序列化总账/明细账行。"""
    return LedgerEntryResponse(
        voucher_id=row.voucher_id,
        voucher_number=row.voucher_number,
        voucher_date=row.voucher_date,
        period_name=row.period_name,
        subject_code=row.subject_code,
        subject_name=row.subject_name,
        debit_amount=row.debit_amount,
        credit_amount=row.credit_amount,
        summary=row.summary,
        description=row.description,
    )


def _serialize_bank_transaction(transaction) -> BankTransactionResponse:
    """序列化银行流水。"""
    return BankTransactionResponse(
        transaction_id=transaction.transaction_id,
        transaction_date=transaction.transaction_date,
        direction=transaction.direction,
        amount=transaction.amount,
        account_name=transaction.account_name,
        counterparty=transaction.counterparty,
        summary=transaction.summary,
        status=transaction.status,
        linked_voucher_id=transaction.linked_voucher_id,
    )


# ============================================================================
# 应用实例（由 uvicorn 直接加载）
# ============================================================================

# 使用 __getattr__ 实现真正的延迟初始化：
# - 模块被 import 时 app 尚不存在
# - 首次访问 app 属性时（uvicorn 加载时）才创建真实 app
# - 测试环境直接调用 create_app() 手动构造，不依赖本模块级属性
def __getattr__(name: str) -> FastAPI:
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_app: FastAPI | None = None
