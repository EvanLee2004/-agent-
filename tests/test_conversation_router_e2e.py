"""DeerFlow 接入后的会话与财务工具测试。"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.query_vouchers_tool import query_vouchers_tool
from accounting.record_voucher_router import RecordVoucherRouter
from accounting.record_voucher_tool import record_voucher_tool
from accounting.sqlite_chart_of_accounts_repository import SQLiteChartOfAccountsRepository
from accounting.sqlite_journal_repository import SQLiteJournalRepository
from app.application_bootstrapper import ApplicationBootstrapper
from audit.audit_service import AuditService
from audit.audit_voucher_router import AuditVoucherRouter
from audit.audit_voucher_tool import audit_voucher_tool
from cashier.cashier_service import CashierService
from cashier.query_cash_transactions_router import QueryCashTransactionsRouter
from cashier.query_cash_transactions_tool import query_cash_transactions_tool
from cashier.record_cash_transaction_router import RecordCashTransactionRouter
from cashier.record_cash_transaction_tool import record_cash_transaction_tool
from cashier.sqlite_cashier_repository import SQLiteCashierRepository
from configuration.llm_configuration import LlmConfiguration
from conversation.conversation_request import ConversationRequest
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from conversation.tool_use_policy import ToolUsePolicy
from department.collaboration.collaborate_with_department_role_router import CollaborateWithDepartmentRoleRouter
from department.collaboration.department_collaboration_service import DepartmentCollaborationService
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import DepartmentRoleRuntimeRepository
from department.department_runtime_context import DepartmentRuntimeContext
from department.finance_department_agent_assets_service import FinanceDepartmentAgentAssetsService
from department.finance_department_request import FinanceDepartmentRequest
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.finance_department_service import FinanceDepartmentService
from department.workbench.department_workbench_service import DepartmentWorkbenchService
from department.workbench.in_memory_department_workbench_repository import InMemoryDepartmentWorkbenchRepository
from department.workbench.role_trace_factory import RoleTraceFactory
from department.workbench.role_trace_summary_builder import RoleTraceSummaryBuilder
from memory.markdown_memory_store_repository import MarkdownMemoryStoreRepository
from memory.memory_service import MemoryService
from memory.search_memory_router import SearchMemoryRouter
from memory.search_memory_tool import search_memory_tool
from memory.sqlite_memory_index_repository import SQLiteMemoryIndexRepository
from memory.store_memory_router import StoreMemoryRouter
from memory.store_memory_tool import store_memory_tool
from rules.file_rules_repository import FileRulesRepository
from rules.reply_with_rules_router import ReplyWithRulesRouter
from rules.reply_with_rules_tool import reply_with_rules_tool
from rules.rules_service import RulesService
from runtime.deerflow.deerflow_client_factory import DeerFlowClientFactory
from runtime.deerflow.deerflow_department_role_runtime_repository import DeerFlowDepartmentRoleRuntimeRepository
from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets
from runtime.deerflow.deerflow_runtime_assets_service import DeerFlowRuntimeAssetsService
from runtime.deerflow.finance_department_tool_context import FinanceDepartmentToolContext
from runtime.deerflow.finance_department_tool_context_registry import FinanceDepartmentToolContextRegistry
from tax.calculate_tax_router import CalculateTaxRouter
from tax.calculate_tax_tool import calculate_tax_tool
from tax.tax_service import TaxService


class FakeDeerFlowClient:
    """用于验证 DeerFlow 角色仓储的测试替身。"""

    def __init__(self, reply_text: str):
        self._reply_text = reply_text
        self.calls: list[tuple[str, str | None]] = []

    def chat(self, message: str, *, thread_id: str | None = None) -> str:
        """记录调用并返回预设文本。"""
        self.calls.append((message, thread_id))
        return self._reply_text


class FakeDeerFlowClientFactory:
    """用于验证 DeerFlow 角色仓储装配行为的测试替身。"""

    def __init__(self, client: FakeDeerFlowClient):
        self._client = client
        self.assets: DeerFlowRuntimeAssets | None = None
        self.role_names: list[str] = []

    def create_client(
        self,
        assets: DeerFlowRuntimeAssets,
        agent_name: str,
    ) -> FakeDeerFlowClient:
        """返回预设 client，并记录接收到的参数。"""
        self.assets = assets
        self.role_names.append(agent_name)
        return self._client


class StubDepartmentRoleRuntimeRepository(DepartmentRoleRuntimeRepository):
    """用于会话边界测试的角色运行时替身。"""

    def reply(self, request: DepartmentRoleRequest) -> DepartmentRoleResponse:
        """直接回显线程与角色信息。"""
        return DepartmentRoleResponse(
            role_name=request.role_name,
            reply_text=f"role={request.role_name}; thread={request.thread_id}; input={request.user_input}",
            collaboration_depth=request.collaboration_depth,
        )


class StubFinanceDepartmentService(FinanceDepartmentService):
    """用于会话边界测试的部门服务替身。"""

    def __init__(self):
        pass

    def reply(self, request: FinanceDepartmentRequest):
        from department.finance_department_response import FinanceDepartmentResponse
        from department.workbench.role_trace import RoleTrace

        return FinanceDepartmentResponse(
            reply_text=f"thread={request.thread_id}; input={request.user_input}",
            role_traces=[
                RoleTrace(
                    role_name="finance-coordinator",
                    display_name="CoordinatorAgent",
                    requested_by=None,
                    goal=request.user_input,
                    thinking_summary="已接收并汇总请求。",
                    depth=0,
                )
            ],
        )


class ConversationRouterEndToEndTest(unittest.TestCase):
    """DeerFlow 接入后的主链路测试。"""

    def tearDown(self) -> None:
        """重置全局上下文，避免跨测试污染。"""
        FinanceDepartmentToolContextRegistry.reset()

    def test_runtime_assets_service_writes_minimal_deerflow_files(self):
        """验证 DeerFlow 运行时资产文件可生成且结构正确。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            skills_root = Path(temp_dir) / "skills"
            skills_root.mkdir(parents=True, exist_ok=True)
            configuration = LlmConfiguration(
                provider_name="minimax",
                model_name="MiniMax-M2.7",
                base_url="https://api.minimaxi.com/v1",
                api_key="test-key",
            )
            assets = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog()),
                runtime_root=runtime_root,
                skills_root=skills_root,
            ).prepare_assets(configuration)

            config_data = yaml.safe_load(assets.config_path.read_text(encoding="utf-8"))
            extensions_data = json.loads(assets.extensions_config_path.read_text(encoding="utf-8"))

            self.assertEqual(config_data["models"][0]["model"], "MiniMax-M2.7")
            self.assertEqual(config_data["tools"][0]["name"], "collaborate_with_department_role")
            self.assertEqual(config_data["skills"]["path"], str(skills_root.resolve()))
            self.assertEqual(extensions_data["skills"]["finance-core"]["enabled"], True)
            self.assertEqual(extensions_data["skills"]["cashier"]["enabled"], True)
            self.assertEqual(assets.runtime_home, (runtime_root / "home").resolve())
            coordinator_config = runtime_root / "home" / "agents" / "finance-coordinator" / "config.yaml"
            cashier_config = runtime_root / "home" / "agents" / "finance-cashier" / "config.yaml"
            self.assertTrue(coordinator_config.exists())
            self.assertTrue(cashier_config.exists())

    def test_deerflow_public_client_can_read_generated_skills(self):
        """验证公开 DeerFlowClient 能读取当前部门全部 skill。"""
        configuration = LlmConfiguration(
            provider_name="minimax",
            model_name="MiniMax-M2.7",
            base_url="https://api.minimaxi.com/v1",
            api_key="test-key",
        )
        assets = DeerFlowRuntimeAssetsService(
            FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog())
        ).prepare_assets(configuration)

        client = DeerFlowClientFactory().create_client(assets, "finance-coordinator")
        skills_payload = client.list_skills()

        skill_names = {item["name"] for item in skills_payload["skills"]}
        self.assertTrue(
            {
                "finance-core",
                "coordinator",
                "cashier",
                "bookkeeping",
                "policy-research",
                "tax",
                "audit",
            }.issubset(skill_names)
        )
        self.assertEqual(os.environ["DEER_FLOW_HOME"], str(assets.runtime_home))

    def test_deerflow_tool_registry_loads_custom_finance_tools(self):
        """验证 DeerFlow 能从配置中加载全部财务工具。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self._register_finance_tool_context(Path(temp_dir))
            configuration = LlmConfiguration(
                provider_name="minimax",
                model_name="MiniMax-M2.7",
                base_url="https://api.minimaxi.com/v1",
                api_key="test-key",
            )
            assets = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog())
            ).prepare_assets(configuration)

            from deerflow.tools import get_available_tools

            DeerFlowClientFactory().create_client(assets, "finance-coordinator")
            tool_names = {tool.name for tool in get_available_tools(include_mcp=False)}

            self.assertTrue(
                {
                    "collaborate_with_department_role",
                    "record_voucher",
                    "query_vouchers",
                    "record_cash_transaction",
                    "query_cash_transactions",
                    "calculate_tax",
                    "audit_voucher",
                    "store_memory",
                    "search_memory",
                    "reply_with_rules",
                }.issubset(tool_names)
            )

    def test_record_voucher_and_query_tools_complete_bookkeeping_flow(self):
        """验证记账和查账工具可完成主业务闭环。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self._register_finance_tool_context(Path(temp_dir))

            record_result = json.loads(
                record_voucher_tool.invoke(
                    {
                        "voucher_date": "2024-03-01",
                        "summary": "客户拜访午餐费",
                        "source_text": "报销差旅费120元，日期2024-03-01，说明客户拜访午餐",
                        "lines": [
                            {
                                "subject_code": "6602",
                                "subject_name": "管理费用",
                                "debit_amount": 120,
                                "credit_amount": 0,
                                "description": "客户拜访午餐",
                            },
                            {
                                "subject_code": "1001",
                                "subject_name": "库存现金",
                                "debit_amount": 0,
                                "credit_amount": 120,
                                "description": "客户拜访午餐",
                            },
                        ],
                    }
                )
            )
            query_result = json.loads(query_vouchers_tool.invoke({}))

            self.assertEqual(record_result["success"], True)
            self.assertEqual(record_result["payload"]["voucher_id"], 1)
            self.assertEqual(query_result["payload"]["count"], 1)
            self.assertEqual(query_result["payload"]["items"][0]["summary"], "客户拜访午餐费")

    def test_cashier_tools_return_structured_results(self):
        """验证资金事实工具返回结构化结果。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self._register_finance_tool_context(Path(temp_dir))

            record_result = json.loads(
                record_cash_transaction_tool.invoke(
                    {
                        "transaction_date": "2024-03-01",
                        "direction": "payment",
                        "amount": 120,
                        "account_name": "工商银行基本户",
                        "summary": "支付客户拜访午餐报销",
                        "counterparty": "李明",
                    }
                )
            )
            query_result = json.loads(query_cash_transactions_tool.invoke({}))

            self.assertEqual(record_result["success"], True)
            self.assertEqual(query_result["payload"]["count"], 1)
            self.assertEqual(query_result["payload"]["items"][0]["direction"], "payment")

    def test_tax_and_audit_tools_return_structured_results(self):
        """验证税务和审核工具返回结构化结果。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self._register_finance_tool_context(Path(temp_dir))
            record_voucher_tool.invoke(
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
                }
            )

            tax_result = json.loads(
                calculate_tax_tool.invoke(
                    {
                        "tax_type": "vat",
                        "taxpayer_type": "small_scale_vat_taxpayer",
                        "amount": 10000,
                        "includes_tax": False,
                        "description": "小规模纳税人销售货物",
                    }
                )
            )
            audit_result = json.loads(audit_voucher_tool.invoke({"target": "latest"}))

            self.assertEqual(tax_result["success"], True)
            self.assertEqual(tax_result["payload"]["payable_tax"], 100.0)
            self.assertEqual(audit_result["success"], True)
            self.assertEqual(audit_result["payload"]["risk_level"], "high")

    def test_memory_and_rules_tools_cooperate(self):
        """验证记忆工具与规则工具可协同工作。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self._register_finance_tool_context(Path(temp_dir))

            store_result = json.loads(
                store_memory_tool.invoke(
                    {
                        "scope": "long_term",
                        "category": "preference",
                        "content": "用户希望报销说明默认写得简洁。",
                    }
                )
            )
            search_result = json.loads(search_memory_tool.invoke({"query": "报销说明怎么写"}))
            rules_result = json.loads(reply_with_rules_tool.invoke({"question": "你记住了什么？"}))

            self.assertEqual(store_result["success"], True)
            self.assertEqual(search_result["payload"]["count"], 1)
            self.assertIn("memory_notice", rules_result["payload"])

    def test_deerflow_role_runtime_repository_uses_thread_identifier(self):
        """验证 DeerFlow 角色运行时仓储会透传线程标识。"""
        fake_client = FakeDeerFlowClient("你好，我是财务部门助手。")
        fake_factory = FakeDeerFlowClientFactory(fake_client)

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            skills_root = Path(temp_dir) / "skills"
            skills_root.mkdir(parents=True, exist_ok=True)
            repository = DeerFlowDepartmentRoleRuntimeRepository(
                configuration=LlmConfiguration(
                    provider_name="minimax",
                    model_name="MiniMax-M2.7",
                    base_url="https://api.minimaxi.com/v1",
                    api_key="test-key",
                ),
                runtime_assets_service=DeerFlowRuntimeAssetsService(
                    runtime_root=runtime_root,
                    skills_root=skills_root,
                    department_agent_assets_service=FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog()),
                ),
                client_factory=fake_factory,
                runtime_context=DepartmentRuntimeContext(),
                reply_text_sanitizer=ReplyTextSanitizer(),
            )
            response = repository.reply(
                DepartmentRoleRequest(
                    role_name="finance-coordinator",
                    user_input="你好",
                    thread_id="thread-123",
                )
            )

            self.assertEqual(response.reply_text, "你好，我是财务部门助手。")
            self.assertEqual(fake_client.calls[0], ("你好", "thread-123"))
            self.assertEqual(fake_factory.role_names, ["finance-coordinator"])

    def test_conversation_router_returns_department_reply_and_trace(self):
        """验证会话层只负责边界收口和思考摘要转发。"""
        router = ConversationRouter(
            ConversationService(
                StubFinanceDepartmentService(),
                ReplyTextSanitizer(),
            )
        )
        response = router.handle(ConversationRequest(user_input="你好", thread_id="cli-1"))
        self.assertEqual(response.reply_text, "thread=cli-1; input=你好")
        self.assertEqual(len(response.role_traces), 1)
        self.assertEqual(response.role_traces[0].display_name, "CoordinatorAgent")

    def test_conversation_service_strips_internal_thinking_text(self):
        """验证会话服务会剔除底层角色泄漏的内部思考片段。"""
        from department.finance_department_response import FinanceDepartmentResponse
        from department.workbench.role_trace import RoleTrace

        class ThinkingFinanceDepartmentService(StubFinanceDepartmentService):
            """返回带思考片段的部门服务替身。"""

            def reply(self, request: FinanceDepartmentRequest):
                return FinanceDepartmentResponse(
                    reply_text="<think>内部思考</think>\n\n你好，已收到。",
                    role_traces=[
                        RoleTrace(
                            role_name="finance-coordinator",
                            display_name="CoordinatorAgent",
                            requested_by=None,
                            goal=request.user_input,
                            thinking_summary="已读取请求。",
                            depth=0,
                        )
                    ],
                )

        service = ConversationService(
            ThinkingFinanceDepartmentService(),
            ReplyTextSanitizer(),
        )
        response = service.reply(
            ConversationRequest(
                user_input="你好",
                thread_id="cli-2",
            )
        )
        self.assertEqual(response.reply_text, "你好，已收到。")
        self.assertEqual(len(response.role_traces), 1)

    def _register_finance_tool_context(self, temp_path: Path) -> None:
        """构造并注册财务工具上下文。"""
        database_path = str(temp_path / "ledger.db")
        journal_repository = SQLiteJournalRepository(database_path)
        chart_repository = SQLiteChartOfAccountsRepository(database_path)
        chart_service = ChartOfAccountsService(chart_repository)
        cashier_repository = SQLiteCashierRepository(database_path)
        ApplicationBootstrapper(
            chart_of_accounts_repository=chart_repository,
            journal_repository=journal_repository,
            chart_of_accounts_service=chart_service,
            cashier_repository=cashier_repository,
        ).initialize()
        accounting_service = AccountingService(journal_repository, chart_service)
        cashier_service = CashierService(cashier_repository)
        memory_store_repository = MarkdownMemoryStoreRepository(
            long_term_memory_file=temp_path / "MEMORY.md",
            daily_memory_dir=temp_path / "memory",
        )
        memory_index_repository = SQLiteMemoryIndexRepository(
            temp_path / ".runtime" / "memory" / "memory_search.sqlite"
        )
        memory_service = MemoryService(memory_store_repository, memory_index_repository)
        rules_service = RulesService(FileRulesRepository())
        runtime_context = DepartmentRuntimeContext()
        workbench_service = DepartmentWorkbenchService(
            InMemoryDepartmentWorkbenchRepository()
        )
        role_catalog = FinanceDepartmentRoleCatalog()
        collaboration_service = DepartmentCollaborationService(
            role_catalog=role_catalog,
            runtime_repository=StubDepartmentRoleRuntimeRepository(),
            workbench_service=workbench_service,
            runtime_context=runtime_context,
            role_trace_factory=RoleTraceFactory(RoleTraceSummaryBuilder()),
        )
        workbench_service.start_turn("test-thread", "测试用户请求")
        FinanceDepartmentToolContextRegistry.register(
            FinanceDepartmentToolContext(
                record_voucher_router=RecordVoucherRouter(accounting_service),
                query_vouchers_router=QueryVouchersRouter(accounting_service),
                calculate_tax_router=CalculateTaxRouter(TaxService()),
                audit_voucher_router=AuditVoucherRouter(AuditService(journal_repository)),
                record_cash_transaction_router=RecordCashTransactionRouter(cashier_service),
                query_cash_transactions_router=QueryCashTransactionsRouter(cashier_service),
                store_memory_router=StoreMemoryRouter(memory_service),
                search_memory_router=SearchMemoryRouter(memory_service),
                reply_with_rules_router=ReplyWithRulesRouter(
                    rules_service,
                    memory_service,
                    ToolUsePolicy(),
                ),
                collaborate_with_department_role_router=CollaborateWithDepartmentRoleRouter(
                    collaboration_service
                ),
            )
        )
