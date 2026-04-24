"""crewAI 会计部门运行时仓储。"""

from typing import Any

from configuration.llm_configuration import LlmConfiguration
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.department_error import DepartmentError
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.department_runtime_context import DepartmentRuntimeContext
from department.llm_usage import LlmUsage
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.audit_voucher_tool import audit_voucher_tool
from runtime.crewai.execution_event_scope import open_execution_event_scope
from runtime.crewai.query_chart_of_accounts_tool import query_chart_of_accounts_tool
from runtime.crewai.query_vouchers_tool import query_vouchers_tool
from runtime.crewai.record_voucher_tool import record_voucher_tool


ACCOUNTING_MANAGER_ROLE = "accounting-manager"


class CrewAIAccountingRuntimeRepository(DepartmentRoleRuntimeRepository):
    """基于 crewAI 执行一轮会计部门协作。

    本仓储是项目与 crewAI 的唯一主链路适配点。它只负责三件事：

    1. 将项目模型配置转换成 crewAI `LLM`。
    2. 构造纯会计核算部门的 Agent/Task/Crew。
    3. 把工具包装器收集到的执行事件转换成部门层响应。

    会计规则、凭证落库、查账和审核仍由 accounting/audit 业务模块负责。
    这样运行时可以替换，但业务事实口径不会散落在 Agent prompt 里。
    """

    def __init__(
        self,
        configuration: LlmConfiguration,
        runtime_context: DepartmentRuntimeContext,
        reply_text_sanitizer: ReplyTextSanitizer,
    ):
        self._configuration = configuration
        self._runtime_context = runtime_context
        self._reply_text_sanitizer = reply_text_sanitizer

    def reply(self, request: DepartmentRoleRequest) -> DepartmentRoleResponse:
        """调用 crewAI 会计部门并返回最终回复。"""
        try:
            with self._runtime_context.open_scope(
                role_name=request.role_name,
                thread_id=request.thread_id,
                collaboration_depth=request.collaboration_depth,
            ):
                with open_execution_event_scope() as execution_events:
                    self._append_accounting_task_events(execution_events)
                    crew = self._build_crew()
                    crew_output = crew.kickoff(inputs={"user_input": request.user_input})
                    reply_text = self._extract_reply_text(crew_output)
                    usage = self._extract_usage(crew_output)
                    execution_events.append(
                        ExecutionEvent(
                            event_type=ExecutionEventType.FINAL_REPLY,
                            tool_name="",
                            summary=reply_text,
                        )
                    )
        except Exception as error:
            raise DepartmentError(f"会计部门运行失败: {str(error)}") from error

        if not reply_text.strip():
            raise DepartmentError("会计部门未返回有效回复")

        return DepartmentRoleResponse(
            role_name=request.role_name,
            reply_text=self._reply_text_sanitizer.sanitize(reply_text.strip()),
            collaboration_depth=request.collaboration_depth,
            execution_events=execution_events,
            usage=usage,
        )

    def _build_crew(self):
        """构造 crewAI 会计部门。

        采用 sequential 而不是 hierarchical，是因为当前产品已经收窄为纯会计核算。
        固定的“判断任务 → 执行记账/查账 → 复核并回复”流程比动态 manager 委派更稳定，
        也更容易把用户可见历史投影成可审计步骤。
        """
        from crewai import Agent, Crew, LLM, Process, Task

        model = self._configuration.get_default_model()
        runtime_configuration = self._configuration.runtime_configuration
        llm = LLM(
            model=model.model_name,
            api_key=model.api_key,
            base_url=model.base_url,
            temperature=model.temperature,
            timeout=model.request_timeout,
            max_tokens=model.max_tokens,
        )

        manager = Agent(
            role="accounting-manager",
            goal="判断用户请求是否属于会计核算，并给出明确处理路径。",
            backstory=(
                "你是小企业会计部门负责人，只处理凭证录入、凭证查询、凭证复核和会计科目查询。"
                "遇到税务、出纳付款、政策研究或非会计核算问题时，必须明确说明当前版本不处理。"
            ),
            llm=llm,
            allow_delegation=False,
            verbose=runtime_configuration.verbose,
        )
        voucher_accountant = Agent(
            role="voucher-accountant",
            goal="基于工具完成凭证录入、凭证查询和会计科目查询。",
            backstory=(
                "你是总账会计。所有凭证录入必须调用 record_voucher；查询凭证必须调用 "
                "query_vouchers；不确定科目时先调用 query_chart_of_accounts，不能编造科目。"
            ),
            llm=llm,
            tools=[
                record_voucher_tool,
                query_vouchers_tool,
                query_chart_of_accounts_tool,
            ],
            allow_delegation=False,
            verbose=runtime_configuration.verbose,
        )
        ledger_reviewer = Agent(
            role="ledger-reviewer",
            goal="复核会计处理结果，并用简明中文给用户最终回复。",
            backstory=(
                "你是会计复核员。用户要求审核时必须调用 audit_voucher；最终回复必须基于工具结果，"
                "不能声称完成未调用工具的写入或审核动作。"
            ),
            llm=llm,
            tools=[audit_voucher_tool, query_vouchers_tool],
            allow_delegation=False,
            verbose=runtime_configuration.verbose,
        )

        triage_task = Task(
            name="accounting_intake",
            description=(
                "分析用户请求：{user_input}\n"
                "只判断其是否属于凭证录入、查账、凭证复核或会计科目查询。"
                "如果属于税务、出纳付款、政策研究或其他范围，输出当前版本不处理的边界说明。"
            ),
            expected_output="给出任务类型、是否在会计核算范围内、建议使用的会计工具。",
            agent=manager,
        )
        execution_task = Task(
            name="accounting_execution",
            description=(
                "根据上一任务结论处理用户请求：{user_input}\n"
                "在范围内时必须使用相应工具；范围外时不要调用工具，直接说明当前只支持会计核算。"
            ),
            expected_output="工具执行结果摘要，或范围外说明。",
            agent=voucher_accountant,
            context=[triage_task],
        )
        review_task = Task(
            name="accounting_review",
            description=(
                "结合前序输出形成最终回复。若用户要求审核凭证，必须调用 audit_voucher。"
                "最终回复要说明已执行的工具动作、关键结果和下一步建议。"
            ),
            expected_output="面向用户的简明中文最终回复。",
            agent=ledger_reviewer,
            context=[triage_task, execution_task],
        )

        return Crew(
            agents=[manager, voucher_accountant, ledger_reviewer],
            tasks=[triage_task, execution_task, review_task],
            process=Process.sequential,
            memory=runtime_configuration.memory_enabled,
            cache=runtime_configuration.cache_enabled,
            verbose=runtime_configuration.verbose,
        )

    def _append_accounting_task_events(
        self,
        execution_events: list[ExecutionEvent],
    ) -> None:
        """记录固定会计流程步骤。

        crewAI 内部 task 事件属于运行时细节，且事件总线为全局对象。这里直接记录
        产品侧认可的三段会计流程，能保持历史展示稳定，也避免把协作摘要绑死在
        crewAI 内部事件字段上。
        """
        for task_name in (
            "accounting_intake",
            "accounting_execution",
            "accounting_review",
        ):
            execution_events.append(
                ExecutionEvent(
                    event_type=ExecutionEventType.TASK_CALL,
                    tool_name=task_name,
                    summary=f"执行 {task_name}",
                )
            )

    def _extract_reply_text(self, crew_output: Any) -> str:
        """从 crewAI 输出中提取最终回复文本。"""
        raw = getattr(crew_output, "raw", None)
        if raw:
            return str(raw)
        return str(crew_output)

    def _extract_usage(self, crew_output: Any) -> LlmUsage | None:
        """从 crewAI 输出中提取 token 使用量。"""
        token_usage = getattr(crew_output, "token_usage", None)
        if token_usage is None:
            return None
        return LlmUsage(
            input_tokens=int(getattr(token_usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(token_usage, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(token_usage, "total_tokens", 0) or 0),
        )
