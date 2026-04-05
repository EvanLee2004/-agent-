"""DeerFlow-first 财务部门 API 入口。

FastAPI 应用，提供与 CLI 共用同一条主链路的会话接口。

依赖注入设计：
- conversation_handler / workbench_service 通过 create_app() 注入
- 生产路径使用 AppServiceFactory.build_api_dependencies() 构造
- 测试路径可注入 mock conversation_handler / mock workbench_service

端点：
- POST /api/conversations/{thread_id}/reply：处理用户输入，返回协作响应
- GET /api/conversations/{thread_id}/turns：获取线程历史（多回合）
- GET /api/conversations/{thread_id}/collaboration-steps：获取协作步骤历史
- GET /api/conversations/{thread_id}/events：获取内部执行事件
- GET /health：健康检查
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Path as FPath

from api.models import (
    CollaborationStepResponse,
    ConversationReplyRequest,
    ConversationReplyResponse,
    ExecutionEventResponse,
    HealthResponse,
    TurnHistoryItem,
)
from conversation.conversation_request import ConversationRequest
from conversation.conversation_response import ConversationResponse

if TYPE_CHECKING:
    from app.conversation_request_handler import AppConversationHandler
    from department.workbench.department_workbench_service import DepartmentWorkbenchService


def create_app(
    conversation_handler: AppConversationHandler | None = None,
    workbench_service: DepartmentWorkbenchService | None = None,
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
        configuration_service: 配置服务（仅在自动构造时使用）。

    Returns:
        配置完成的 FastAPI 应用实例。
    """
    app = FastAPI(
        title="智能财务部门 API",
        description="DeerFlow-first 多 Agent 财务系统，提供记账、审核、税务、出纳等能力。",
        version="1.0.0",
    )

    # ========================================================================
    # 依赖注入：优先使用注入的实例，否则自动构造（生产路径）
    # ========================================================================
    if conversation_handler is None:
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

    # 将依赖存入 app.state，供端点访问
    app.state.conversation_handler = conversation_handler
    app.state.workbench_service = workbench_service

    # ========================================================================
    # 端点定义
    # ========================================================================

    @app.post(
        "/api/conversations/{thread_id}/reply",
        response_model=ConversationReplyResponse,
        summary="处理会话回复",
    )
    def reply_conversation(
        thread_id: str = FPath(..., description="线程标识"),
        request: ConversationReplyRequest = ...,
    ) -> ConversationReplyResponse:
        """处理用户输入，返回 DeerFlow 协作响应。

        内部流程：ConversationRequest → AppConversationHandler.handle() →
        ConversationRouter.handle() → ConversationService.reply() →
        FinanceDepartmentService → DeerFlowDepartmentRoleRuntimeRepository → DeerFlowClient

        注意：
        - thread_id 通过路径参数传入，请求体只包含 user_input
        - 内部异常由 AppConversationHandler 翻译为 HTTP 400/500，不暴露 DeerFlow 细节
        - usage 数据被持久化但不返回给用户
        """
        handler = app.state.conversation_handler
        response: ConversationResponse = handler.handle(
            ConversationRequest(
                user_input=request.user_input,
                thread_id=thread_id,
            )
        )
        return ConversationReplyResponse(
            thread_id=thread_id,
            reply_text=response.reply_text,
            collaboration_steps=[
                CollaborationStepResponse(
                    goal=step.goal,
                    step_type=step.step_type.value,
                    tool_name=step.tool_name,
                    summary=step.summary,
                )
                for step in response.collaboration_steps
            ],
        )

    @app.get(
        "/api/conversations/{thread_id}/turns",
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
        "/api/conversations/{thread_id}/collaboration-steps",
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
        "/api/conversations/{thread_id}/events",
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

    @app.get("/health", response_model=HealthResponse, summary="健康检查")
    def health() -> HealthResponse:
        """返回服务健康状态。"""
        return HealthResponse(status="ok", version="1.0.0")

    return app


# ============================================================================
# 应用实例（由 uvicorn 直接加载）
# ============================================================================

# 使用 __getattr__ 实现真正的延迟初始化：
# - 模块被 import 时 app 尚不存在
# - 首次访问 app 属性时（uvicorn 加载时）才创建真实 app
# - 测试环境直接调用 create_app() 手动构造，不依赖本模块级属性
def __getattr__(name: str):
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_app: FastAPI | None = None
