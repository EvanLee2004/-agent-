"""crewAI 会计部门运行时仓储。"""

from typing import Any

from configuration.llm_configuration import LlmConfiguration
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from conversation.tool_router_response import ToolRouterResponse
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
from runtime.crewai.local_hash_embedding_function import LocalHashEmbeddingFunction
from runtime.crewai.post_voucher_tool import post_voucher_tool
from runtime.crewai.query_account_balance_tool import query_account_balance_tool
from runtime.crewai.query_chart_of_accounts_tool import query_chart_of_accounts_tool
from runtime.crewai.query_bank_transactions_tool import query_bank_transactions_tool
from runtime.crewai.query_ledger_entries_tool import query_ledger_entries_tool
from runtime.crewai.query_trial_balance_tool import query_trial_balance_tool
from runtime.crewai.query_vouchers_tool import query_vouchers_tool
from runtime.crewai.reconcile_bank_transaction_tool import reconcile_bank_transaction_tool
from runtime.crewai.record_bank_transaction_tool import record_bank_transaction_tool
from runtime.crewai.record_voucher_tool import record_voucher_tool
from runtime.crewai.reverse_voucher_tool import reverse_voucher_tool
from runtime.crewai.void_voucher_tool import void_voucher_tool


class CrewAIAccountingRuntimeRepository(DepartmentRoleRuntimeRepository):
    """基于 crewAI 执行一轮财务部门协作。

    本仓储是项目与 crewAI 的唯一主链路适配点。它只负责三件事：

    1. 将项目模型配置转换成 crewAI `LLM`。
    2. 构造会计内核和出纳/银行基础能力的 Agent/Task/Crew。
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
        """调用 crewAI 财务部门并返回最终回复。"""
        try:
            with self._runtime_context.open_scope(thread_id=request.thread_id):
                with open_execution_event_scope() as execution_events:
                    self._append_accounting_task_events(execution_events)
                    crew = self._build_crew(
                        thread_id=request.thread_id,
                        conversation_context=request.conversation_context,
                    )
                    crew_output = crew.kickoff(
                        inputs={
                            "user_input": request.user_input,
                            "conversation_context": (
                                request.conversation_context
                                or "无可用历史上下文。"
                            ),
                        }
                    )
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
            tool_results=self._extract_tool_results(execution_events),
            context_refs=request.context_refs or [],
            usage=usage,
        )

    def _build_crew(self, thread_id: str, conversation_context: str):
        """构造 crewAI 财务部门。

        采用 sequential 而不是 hierarchical，是因为当前阶段先保证会计内核和银行流水
        这两条确定链路可审计。固定的“判断任务 → 会计执行 → 出纳执行 → 复核回复”
        比动态 manager 委派更稳定，也更容易把用户可见历史投影成可审计步骤。
        """
        from crewai import Agent, Crew, LLM, Memory, Process, Task

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
        memory = self._build_memory(
            Memory=Memory,
            llm=llm,
            thread_id=thread_id,
            storage_path=runtime_configuration.memory_storage_path,
        )

        manager = Agent(
            role="accounting-manager",
            goal="判断用户请求是否属于会计核算，并给出明确处理路径。",
            backstory=(
                "你是小企业财务部门负责人，只处理凭证录入、凭证查询、凭证复核、"
                "凭证过账、凭证作废、凭证红冲、会计科目查询、账簿报表、"
                "银行流水记录、银行流水查询和银行流水对账。"
                "遇到税务、政策研究或非财务核算问题时，必须明确说明当前版本不处理。"
            ),
            llm=llm,
            allow_delegation=False,
            verbose=runtime_configuration.verbose,
        )
        voucher_accountant = Agent(
            role="voucher-accountant",
            goal="基于工具完成凭证录入、生命周期处理、账簿查询和会计科目查询。",
            backstory=(
                "你是总账会计。所有凭证录入必须调用 record_voucher；查询凭证必须调用 "
                "query_vouchers；过账、作废、红冲必须调用对应工具；查询余额表、明细账、"
                "试算平衡必须调用报表工具；不确定科目时先调用 query_chart_of_accounts。"
            ),
            llm=llm,
            tools=[
                record_voucher_tool,
                query_vouchers_tool,
                query_chart_of_accounts_tool,
                post_voucher_tool,
                void_voucher_tool,
                reverse_voucher_tool,
                query_account_balance_tool,
                query_ledger_entries_tool,
                query_trial_balance_tool,
            ],
            allow_delegation=False,
            verbose=runtime_configuration.verbose,
        )
        cashier_agent = Agent(
            role="cashier-agent",
            goal="记录、查询和对账银行流水，但不直接修改总账凭证。",
            backstory=(
                "你是出纳。记录收付款必须调用 record_bank_transaction；查询银行流水必须调用 "
                "query_bank_transactions；对账必须调用 reconcile_bank_transaction。"
                "如果需要生成会计凭证，应让总账会计通过 record_voucher 完成。"
            ),
            llm=llm,
            tools=[
                record_bank_transaction_tool,
                query_bank_transactions_tool,
                reconcile_bank_transaction_tool,
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
            tools=[
                audit_voucher_tool,
                query_vouchers_tool,
                query_trial_balance_tool,
                query_account_balance_tool,
            ],
            allow_delegation=False,
            verbose=runtime_configuration.verbose,
        )

        triage_task = Task(
            name="accounting_intake",
            description=(
                "分析用户请求：{user_input}\n"
                "受控历史上下文：\n{conversation_context}\n"
                "只判断其是否属于凭证录入、查账、凭证复核、会计科目查询、"
                "凭证过账、凭证作废、凭证红冲、报表查询、银行流水记录、"
                "银行流水查询或银行流水对账。"
                "如果属于税务、政策研究或其他范围，输出当前版本不处理的边界说明。"
                "如果用户使用“刚才、上一笔、最近一张”等指代，只能把上下文中的候选凭证当作线索。"
            ),
            expected_output="给出任务类型、是否在会计核算范围内、建议使用的会计工具。",
            agent=manager,
        )
        execution_task = Task(
            name="accounting_execution",
            description=(
                "根据上一任务结论处理用户请求：{user_input}\n"
                "受控历史上下文：\n{conversation_context}\n"
                "在范围内时必须使用相应工具；范围外时不要调用工具，直接说明当前只支持"
                "会计核算与银行流水处理。"
                "涉及金额、科目、凭证状态或审核结论时，必须调用工具查询或审核，不能只引用记忆。"
            ),
            expected_output="工具执行结果摘要，或范围外说明。",
            agent=voucher_accountant,
            context=[triage_task],
        )
        cashier_task = Task(
            name="cashier_execution",
            description=(
                "根据前序结论处理出纳/银行相关请求：{user_input}\n"
                "受控历史上下文：\n{conversation_context}\n"
                "如果是银行流水记录、查询或对账，必须调用对应银行工具。"
                "出纳工具只维护资金流水和对账状态，不能声称已经改动总账凭证。"
            ),
            expected_output="银行流水工具执行结果摘要，或说明本轮无出纳动作。",
            agent=cashier_agent,
            context=[triage_task],
        )
        review_task = Task(
            name="accounting_review",
            description=(
                "结合前序输出形成最终回复。若用户要求审核凭证，必须调用 audit_voucher。"
                "最终回复要说明已执行的工具动作、关键结果和下一步建议。"
                "如果使用了历史上下文，必须说明已经通过工具确认过关键财务事实。"
            ),
            expected_output="面向用户的简明中文最终回复。",
            agent=ledger_reviewer,
            context=[triage_task, execution_task, cashier_task],
        )

        return Crew(
            agents=[manager, voucher_accountant, cashier_agent, ledger_reviewer],
            tasks=[triage_task, execution_task, cashier_task, review_task],
            process=Process.sequential,
            memory=memory if runtime_configuration.memory_enabled else False,
            cache=runtime_configuration.cache_enabled,
            verbose=runtime_configuration.verbose,
        )

    def _build_memory(
        self,
        *,
        Memory,
        llm,
        thread_id: str,
        storage_path: str,
    ):
        """构造受控 crewAI Memory。

        memory 的存储路径和 embedding 都由本项目显式提供。这样既满足用户希望启用
        crewAI memory 的要求，又避免默认外部 embedding 在本地私有部署中静默出网。
        """
        return Memory(
            llm=llm,
            storage=storage_path,
            embedder={
                "provider": "custom",
                "config": {
                    "embedding_callable": LocalHashEmbeddingFunction,
                },
            },
            root_scope=f"/thread/{thread_id}",
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
            "cashier_execution",
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

    def _extract_tool_results(
        self,
        execution_events: list[ExecutionEvent],
    ) -> list[ToolRouterResponse]:
        """从工具结果事件中恢复结构化 envelope。"""
        tool_results: list[ToolRouterResponse] = []
        for event in execution_events:
            if event.event_type != ExecutionEventType.TOOL_RESULT:
                continue
            response = ToolRouterResponse.from_tool_message_content(event.summary)
            if response is not None:
                tool_results.append(response)
        return tool_results
