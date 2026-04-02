"""ConversationRouter 端到端测试。"""

import tempfile
import unittest
from pathlib import Path
from typing import Any, Optional

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.record_voucher_router import RecordVoucherRouter
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from app.application_bootstrapper import ApplicationBootstrapper
from audit.audit_service import AuditService
from audit.audit_voucher_router import AuditVoucherRouter
from conversation.conversation_request import ConversationRequest
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.file_prompt_skill_repository import FilePromptSkillRepository
from conversation.prompt_context_service import PromptContextService
from conversation.tool_loop_service import ToolLoopService
from conversation.tool_router_catalog import ToolRouterCatalog
from conversation.tool_use_policy import ToolUsePolicy
from llm.llm_chat_repository import LlmChatRepository
from llm.llm_chat_request import LlmChatRequest
from llm.llm_message import LlmMessage
from llm.llm_response import LlmResponse
from llm.llm_tool_call import LlmToolCall
from memory.markdown_memory_store_repository import MarkdownMemoryStoreRepository
from memory.memory_service import MemoryService
from memory.search_memory_router import SearchMemoryRouter
from memory.sqlite_memory_index_repository import SQLiteMemoryIndexRepository
from memory.store_memory_router import StoreMemoryRouter
from rules.file_rules_repository import FileRulesRepository
from rules.reply_with_rules_router import ReplyWithRulesRouter
from rules.rules_service import RulesService
from tax.calculate_tax_router import CalculateTaxRouter
from tax.tax_request import TaxRequest
from tax.tax_service import TaxService
from tax.tax_type import TaxType
from tax.taxpayer_type import TaxpayerType


def build_tool_response(
    tool_name: str,
    arguments: dict[str, Any],
    call_id: Optional[str] = None,
    content: str = "",
) -> dict[str, Any]:
    """构造测试桩工具响应。"""
    return {
        "content": content,
        "tool_calls": [
            {
                "id": call_id or f"call_{tool_name}",
                "name": tool_name,
                "arguments": arguments,
            }
        ],
    }


class StubLlmChatRepository(LlmChatRepository):
    """按顺序返回预设响应的 LLM 仓储测试桩。"""

    def __init__(self, responses: list[Any]):
        self._responses = responses
        self.calls: list[LlmChatRequest] = []

    def send_chat_request(self, chat_request: LlmChatRequest) -> LlmResponse:
        """返回预设响应。"""
        self.calls.append(chat_request)
        if not self._responses:
            return LlmResponse(
                content="",
                usage={},
                model_name="stub",
                success=False,
                error_message="No more stub responses",
            )

        response = self._responses.pop(0)
        if isinstance(response, str):
            return LlmResponse(
                content=response,
                usage={},
                model_name="stub",
                success=True,
                assistant_message=LlmMessage(role="assistant", content=response),
            )

        if response.get("success", True) is False:
            return LlmResponse(
                content=str(response.get("content", "")),
                usage={},
                model_name="stub",
                success=False,
                error_message=response.get("error_message", "Stub failure"),
            )

        tool_calls = []
        assistant_tool_calls = []
        for item in response.get("tool_calls", []):
            tool_call = LlmToolCall(
                call_id=str(item["id"]),
                tool_name=str(item["name"]),
                arguments=dict(item["arguments"]),
                raw_arguments="{}",
            )
            tool_calls.append(tool_call)
            assistant_tool_calls.append(
                {
                    "id": tool_call.call_id,
                    "type": "function",
                    "function": {"name": tool_call.tool_name, "arguments": "{}"},
                }
            )

        return LlmResponse(
            content=str(response.get("content", "")),
            usage={},
            model_name="stub",
            success=True,
            tool_calls=tool_calls,
            assistant_message=LlmMessage(
                role="assistant",
                content=str(response.get("content", "")),
                tool_calls=assistant_tool_calls,
            ),
        )


class ConversationRouterEndToEndTest(unittest.TestCase):
    """ConversationRouter 端到端测试。"""

    def _build_router_without_bootstrap(
        self,
        temp_path: Path,
        responses: list[Any],
    ) -> tuple[ConversationRouter, SQLiteJournalRepository, MarkdownMemoryStoreRepository, StubLlmChatRepository]:
        """构造未 bootstrap 的路由。"""
        database_path = str(temp_path / "ledger.db")
        journal_repository = SQLiteJournalRepository(database_path)
        chart_repository = SQLiteChartOfAccountsRepository(database_path)
        chart_service = ChartOfAccountsService(chart_repository)
        accounting_service = AccountingService(journal_repository, chart_service)
        tax_service = TaxService()
        audit_service = AuditService(journal_repository)
        memory_store_repository = MarkdownMemoryStoreRepository(
            long_term_memory_file=temp_path / "MEMORY.md",
            daily_memory_dir=temp_path / "memory",
        )
        memory_index_repository = SQLiteMemoryIndexRepository(
            temp_path / ".agent_assets" / "cache" / "memory_search.sqlite"
        )
        memory_service = MemoryService(memory_store_repository, memory_index_repository)
        prompt_skill_repository = FilePromptSkillRepository()
        tool_use_policy = ToolUsePolicy()
        rules_service = RulesService(FileRulesRepository(prompt_skill_repository))
        llm_chat_repository = StubLlmChatRepository(responses)
        tool_router_catalog = ToolRouterCatalog(
            [
                RecordVoucherRouter(accounting_service),
                QueryVouchersRouter(accounting_service),
                CalculateTaxRouter(tax_service),
                AuditVoucherRouter(audit_service),
                StoreMemoryRouter(memory_service),
                SearchMemoryRouter(memory_service),
                ReplyWithRulesRouter(rules_service, memory_service, tool_use_policy),
            ]
        )
        prompt_context_service = PromptContextService(
            prompt_skill_repository,
            memory_service,
            chart_service,
            tool_use_policy,
        )
        router = ConversationRouter(
            ConversationService(
                prompt_context_service,
                ToolLoopService(llm_chat_repository, tool_router_catalog),
            )
        )
        return router, journal_repository, memory_store_repository, llm_chat_repository

    def _build_bootstrapped_router(
        self,
        temp_path: Path,
        responses: list[Any],
    ) -> tuple[ConversationRouter, SQLiteJournalRepository, MarkdownMemoryStoreRepository, StubLlmChatRepository]:
        """构造完成 bootstrap 的路由。"""
        router, journal_repository, memory_store_repository, llm_chat_repository = (
            self._build_router_without_bootstrap(temp_path, responses)
        )
        chart_repository = SQLiteChartOfAccountsRepository(str(temp_path / "ledger.db"))
        chart_service = ChartOfAccountsService(chart_repository)
        ApplicationBootstrapper(
            chart_of_accounts_repository=chart_repository,
            journal_repository=journal_repository,
            chart_of_accounts_service=chart_service,
        ).initialize()
        return router, journal_repository, memory_store_repository, llm_chat_repository

    def test_router_construction_has_no_bootstrap_side_effects(self):
        """验证路由构造不会初始化数据库和记忆文件。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            self._build_router_without_bootstrap(temp_path, [])
            self.assertFalse((temp_path / "ledger.db").exists())
            self.assertFalse((temp_path / "MEMORY.md").exists())

    def test_tax_request_normalizes_common_aliases(self):
        """验证税务请求归一化。"""
        request = TaxRequest.from_dict(
            {
                "tax_type": "增值税",
                "taxpayer_type": "small_scale_vat_taxaxpayer",
                "amount": 10000,
                "includes_tax": False,
            }
        )
        self.assertEqual(request.tax_type, TaxType.VAT)
        self.assertEqual(request.taxpayer_type, TaxpayerType.SMALL_SCALE_VAT)

    def test_accounting_then_query_flow_uses_tool_loop(self):
        """验证记账与查账主路径。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response(
                    "record_voucher",
                    {
                        "voucher_date": "2024-01-15",
                        "summary": "报销客户拜访差旅费",
                        "source_text": "报销差旅费500元，日期2024-01-15，说明客户拜访",
                        "lines": [
                            {
                                "subject_code": "6602",
                                "subject_name": "管理费用",
                                "debit_amount": 500,
                                "credit_amount": 0,
                                "description": "客户拜访差旅费",
                            },
                            {
                                "subject_code": "1001",
                                "subject_name": "库存现金",
                                "debit_amount": 0,
                                "credit_amount": 500,
                                "description": "客户拜访差旅费",
                            },
                        ],
                    },
                ),
                "记账成功 [凭证ID:1] 报销客户拜访差旅费 | 金额 500.00元",
                build_tool_response("query_vouchers", {}),
                "已找到1张凭证：报销客户拜访差旅费，金额500.00元。",
            ]
            router, journal_repository, _, llm_repository = self._build_bootstrapped_router(temp_path, responses)
            record_response = router.handle(ConversationRequest(user_input="报销差旅费500元，日期2024-01-15，说明客户拜访"))
            self.assertIn("记账成功", record_response.reply_text)
            vouchers = journal_repository.list_vouchers(query=__import__("accounting.query_vouchers_query", fromlist=["QueryVouchersQuery"]).QueryVouchersQuery())
            self.assertEqual(len(vouchers), 1)
            self.assertEqual(vouchers[0].summary, "报销客户拜访差旅费")
            query_response = router.handle(ConversationRequest(user_input="查看账目"))
            self.assertIn("报销客户拜访差旅费", query_response.reply_text)
            self.assertEqual(llm_repository.calls[0].tool_choice, "auto")
            self.assertEqual(llm_repository.calls[1].tool_choice, "auto")
            self.assertEqual(llm_repository.calls[2].tool_choice, "auto")

    def test_tax_flow_uses_calculate_tax_tool(self):
        """验证税务流程。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response(
                    "calculate_tax",
                    {
                        "tax_type": "vat",
                        "taxpayer_type": "small_scale_vat_taxpayer",
                        "amount": 10000,
                        "includes_tax": False,
                        "description": "小规模纳税人销售货物",
                    },
                ),
                "税务计算完成：增值税\n- 应纳税额：100.00元\n- 税率：1.00%",
            ]
            router, _, _, _ = self._build_bootstrapped_router(temp_path, responses)
            response = router.handle(ConversationRequest(user_input="小规模纳税人销售货物10000元，需要交多少增值税？"))
            self.assertIn("100.00元", response.reply_text)

    def test_audit_flow_reviews_latest_voucher(self):
        """验证审核流程。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response("audit_voucher", {"target": "latest"}),
                "已审核 1 张凭证，风险等级：high\n- [HIGH] LARGE_AMOUNT: 金额超过阈值。",
            ]
            router, journal_repository, _, _ = self._build_bootstrapped_router(temp_path, responses)
            record_router, _, _, _ = self._build_bootstrapped_router(
                temp_path,
                [
                    build_tool_response(
                        "record_voucher",
                        {
                            "voucher_date": "2024-02-01",
                            "summary": "设备采购付款",
                            "source_text": "支付设备采购款60000元",
                            "lines": [
                                {
                                    "subject_code": "6602",
                                    "subject_name": "管理费用",
                                    "debit_amount": 60000,
                                    "credit_amount": 0,
                                    "description": "设备采购付款",
                                },
                                {
                                    "subject_code": "1002",
                                    "subject_name": "银行存款",
                                    "debit_amount": 0,
                                    "credit_amount": 60000,
                                    "description": "设备采购付款",
                                },
                            ],
                        },
                    ),
                    "ok",
                ],
            )
            record_router.handle(ConversationRequest(user_input="支付设备采购款60000元"))
            response = router.handle(ConversationRequest(user_input="审核最新凭证"))
            self.assertIn("风险等级：high", response.reply_text)

    def test_memory_tools_store_and_reuse_long_term_memory(self):
        """验证显式记忆写入和复用。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response(
                    "store_memory",
                    {"scope": "long_term", "category": "preference", "content": "用户希望报销说明默认写得简洁。"},
                ),
                "我记住了：以后默认把报销说明写得简洁些。",
                build_tool_response("search_memory", {"query": "报销说明 简洁", "limit": 5}),
                "之后我会尽量把报销说明写得更简洁。",
            ]
            router, _, memory_store_repository, llm_repository = self._build_bootstrapped_router(temp_path, responses)
            remember_response = router.handle(ConversationRequest(user_input="记住：我以后喜欢把报销说明写得简洁一点。"))
            self.assertIn("记住", remember_response.reply_text)
            long_term_memory_file = temp_path / "MEMORY.md"
            self.assertTrue(long_term_memory_file.exists())
            self.assertIn("用户希望报销说明默认写得简洁。", long_term_memory_file.read_text(encoding="utf-8"))
            second_response = router.handle(ConversationRequest(user_input="以后你会怎么写报销说明？"))
            self.assertIn("简洁", second_response.reply_text)
            self.assertIn("用户希望报销说明默认写得简洁。", llm_repository.calls[2].messages[0].content)

    def test_memory_recall_prompt_does_not_preload_memory_fact(self):
        """验证记忆召回场景不会预加载具体记忆内容。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            remembered_content = "用户希望报销说明默认写得简洁。"
            responses = [
                build_tool_response(
                    "store_memory",
                    {"scope": "long_term", "category": "preference", "content": remembered_content},
                ),
                "我记住了：以后默认把报销说明写得简洁些。",
                build_tool_response("search_memory", {"query": "我之前让你记住了什么", "limit": 5}),
                "你之前让我记住：用户希望报销说明默认写得简洁。",
            ]
            router, _, _, llm_repository = self._build_bootstrapped_router(temp_path, responses)
            router.handle(ConversationRequest(user_input="记住：我以后喜欢把报销说明写得简洁一点。"))
            recall_response = router.handle(ConversationRequest(user_input="我之前让你记住了什么？"))
            self.assertIn("简洁", recall_response.reply_text)
            initial_prompt = llm_repository.calls[2].messages[0].content
            self.assertIn("记忆召回约束", initial_prompt)
            self.assertNotIn(remembered_content, initial_prompt)
            self.assertEqual(llm_repository.calls[2].tool_choice, "auto")

    def test_rules_questions_use_reply_with_rules_tool(self):
        """验证规则问题仍走工具链。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response("reply_with_rules", {"question": "报销金额超过50000元怎么办？"}),
                "超过50000元的凭证需要审核。",
            ]
            router, _, _, llm_repository = self._build_bootstrapped_router(temp_path, responses)
            response = router.handle(ConversationRequest(user_input="报销金额超过50000元怎么办？"))
            self.assertIn("需要审核", response.reply_text)
            tool_names = [tool["function"]["name"] for tool in llm_repository.calls[0].tools]
            self.assertIn("reply_with_rules", tool_names)

    def test_final_reply_strips_think_blocks(self):
        """验证最终回复不会暴露 think 块。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response("query_vouchers", {}),
                "<think>\n先整理一下结果。\n</think>\n\n当前账目为空。",
            ]
            router, _, _, _ = self._build_bootstrapped_router(temp_path, responses)
            response = router.handle(ConversationRequest(user_input="查看账目"))
            self.assertEqual(response.reply_text, "当前账目为空。")

    def test_router_allows_free_chat_without_tool_call(self):
        """验证普通闲聊允许直接自然回复。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            router, _, _, llm_repository = self._build_bootstrapped_router(
                temp_path,
                ["你好，我是智能会计助手，可以帮你处理记账、查账、税务和审核问题。"],
            )
            response = router.handle(ConversationRequest(user_input="你好"))
            self.assertIn("智能会计助手", response.reply_text)
            self.assertEqual(llm_repository.calls[0].tool_choice, "auto")

    def test_full_business_flow_runs_end_to_end(self):
        """验证完整业务链路。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response("store_memory", {"scope": "long_term", "category": "preference", "content": "用户希望报销说明默认写得简洁。"}),
                "我记住了：以后默认把报销说明写得简洁些。",
                build_tool_response(
                    "record_voucher",
                    {
                        "voucher_date": "2024-03-01",
                        "summary": "报销客户拜访差旅费",
                        "source_text": "报销差旅费500元，日期2024-03-01，说明客户拜访",
                        "lines": [
                            {"subject_code": "6602", "subject_name": "管理费用", "debit_amount": 500, "credit_amount": 0, "description": "客户拜访差旅费"},
                            {"subject_code": "1001", "subject_name": "库存现金", "debit_amount": 0, "credit_amount": 500, "description": "客户拜访差旅费"},
                        ],
                    },
                ),
                "记账成功 [凭证ID:1] 报销客户拜访差旅费 | 金额 500.00元",
                build_tool_response("query_vouchers", {}),
                "已找到1张凭证：报销客户拜访差旅费，金额500.00元。",
                build_tool_response(
                    "calculate_tax",
                    {
                        "tax_type": "vat",
                        "taxpayer_type": "small_scale_vat_taxpayer",
                        "amount": 10000,
                        "includes_tax": False,
                        "description": "小规模纳税人销售货物",
                    },
                ),
                "税务计算完成：增值税\n- 应纳税额：100.00元",
                build_tool_response("audit_voucher", {"target": "latest"}),
                "已审核 1 张凭证，风险等级：low\n- 未发现明显异常",
                build_tool_response("search_memory", {"query": "报销说明 简洁", "limit": 5}),
                "之后我会尽量把报销说明写得更简洁。",
                build_tool_response("reply_with_rules", {"question": "超过50000元的凭证需要怎么处理？"}),
                "超过50000元的凭证需要审核。",
            ]
            router, journal_repository, _, _ = self._build_bootstrapped_router(temp_path, responses)
            self.assertIn("记住", router.handle(ConversationRequest(user_input="记住：我以后喜欢把报销说明写得简洁一点。")).reply_text)
            self.assertIn("记账成功", router.handle(ConversationRequest(user_input="报销差旅费500元，日期2024-03-01，说明客户拜访")).reply_text)
            self.assertIn("报销客户拜访差旅费", router.handle(ConversationRequest(user_input="查看账目")).reply_text)
            self.assertIn("100.00元", router.handle(ConversationRequest(user_input="小规模纳税人销售货物10000元，需要交多少增值税？")).reply_text)
            self.assertIn("风险等级：low", router.handle(ConversationRequest(user_input="审核最新凭证")).reply_text)
            self.assertIn("简洁", router.handle(ConversationRequest(user_input="以后你会怎么写报销说明？")).reply_text)
            self.assertIn("需要审核", router.handle(ConversationRequest(user_input="超过50000元的凭证需要怎么处理？")).reply_text)
            self.assertEqual(len(journal_repository.list_vouchers(query=__import__("accounting.query_vouchers_query", fromlist=["QueryVouchersQuery"]).QueryVouchersQuery())), 1)
