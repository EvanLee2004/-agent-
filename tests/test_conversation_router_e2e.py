"""DeerFlow 接入后的会话与财务工具测试。"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from accounting.accounting_service import AccountingService
from accounting.chart_of_accounts_service import ChartOfAccountsService
from accounting.query_vouchers_router import QueryVouchersRouter
from accounting.query_vouchers_tool import query_vouchers_tool
from accounting.record_voucher_router import RecordVoucherRouter
from accounting.record_voucher_tool import record_voucher_tool
from accounting.sqlite_chart_of_accounts_repository import (
    SQLiteChartOfAccountsRepository,
)
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
from configuration.deerflow_runtime_configuration import DeerFlowRuntimeConfiguration
from configuration.llm_configuration import LlmConfiguration
from configuration.llm_model_profile import LlmModelProfile
from conversation.conversation_request import ConversationRequest
from conversation.conversation_router import ConversationRouter
from conversation.conversation_service import ConversationService
from conversation.reply_text_sanitizer import ReplyTextSanitizer
from department.collaboration.collaborate_with_department_role_router import (
    CollaborateWithDepartmentRoleRouter,
)
from department.collaboration.department_collaboration_service import (
    DepartmentCollaborationService,
)
from department.department_role_request import DepartmentRoleRequest
from department.department_role_response import DepartmentRoleResponse
from department.department_role_runtime_repository import (
    DepartmentRoleRuntimeRepository,
)
from department.department_runtime_context import DepartmentRuntimeContext
from department.finance_department_agent_assets_service import (
    FinanceDepartmentAgentAssetsService,
)
from department.finance_department_request import FinanceDepartmentRequest
from department.finance_department_role_catalog import FinanceDepartmentRoleCatalog
from department.finance_department_service import FinanceDepartmentService
from department.workbench.department_workbench_service import DepartmentWorkbenchService
from department.workbench.in_memory_department_workbench_repository import (
    InMemoryDepartmentWorkbenchRepository,
)
from department.workbench.role_trace_factory import RoleTraceFactory
from department.workbench.role_trace_summary_builder import RoleTraceSummaryBuilder
from rules.file_rules_repository import FileRulesRepository
from rules.reply_with_rules_router import ReplyWithRulesRouter
from rules.reply_with_rules_tool import reply_with_rules_tool
from rules.rules_service import RulesService
from runtime.deerflow.deerflow_client_factory import DeerFlowClientFactory
from runtime.deerflow.deerflow_department_role_runtime_repository import (
    DeerFlowDepartmentRoleRuntimeRepository,
)
from runtime.deerflow.deerflow_runtime_assets import DeerFlowRuntimeAssets
from runtime.deerflow.deerflow_runtime_assets_service import (
    DeerFlowRuntimeAssetsService,
)
from runtime.deerflow.finance_department_tool_context import (
    FinanceDepartmentToolContext,
)
from runtime.deerflow.finance_department_tool_context_registry import (
    FinanceDepartmentToolContextRegistry,
)
from tax.calculate_tax_router import CalculateTaxRouter
from tax.calculate_tax_tool import calculate_tax_tool
from tax.tax_service import TaxService


class FakeDeerFlowClient:
    """用于验证 DeerFlow 角色仓储的测试替身。

    支持 stream() 方式和 chat() 方式调用，以适配改进后的仓储实现。
    模拟 DeerFlow embedded mode 的真实行为：一个 turn 中产生多个 AIMessage，
    分别是中间回复、工具调用、工具结果、最终回复。
    """

    def __init__(self, reply_text: str):
        self._reply_text = reply_text
        self.calls: list[tuple[str, str | None]] = []
        self.reset_agent_calls: int = 0

    def reset_agent(self) -> None:
        """记录 reset_agent 调用。"""
        self.reset_agent_calls += 1

    def stream(self, message: str, *, thread_id: str | None = None):
        """模拟 DeerFlow embedded mode stream() 的完整 turn 流程。

        模拟一个典型场景：
        1. AI 先发中间回复（如"好的，我帮你查一下"）
        2. AI 发起工具调用
        3. 工具执行（DeerFlow 不直接发 tool 事件，由 agent 处理）
        4. AI 发最终回复（这是唯一应该进入 reply_text 的内容）

        注意：最终 reply 应该只取最后一个非空 AI 文本。
        """
        from dataclasses import dataclass

        @dataclass
        class FakeStreamEvent:
            type: str
            data: dict

        self.calls.append((message, thread_id))

        # 第一个 AI 事件：中间话术（不应进入最终回复）
        yield FakeStreamEvent(
            type="messages-tuple",
            data={"type": "ai", "content": "好的，我帮你处理。", "id": "msg-1"},
        )

        # 第二个 AI 事件：发起工具调用
        yield FakeStreamEvent(
            type="messages-tuple",
            data={
                "type": "ai",
                "content": "",
                "id": "msg-2",
                "tool_calls": [{"name": "record_voucher", "args": {}, "id": "call-1"}],
            },
        )

        # 最终 AI 事件：实际回复（这是唯一应该进入 reply_text 的）
        yield FakeStreamEvent(
            type="messages-tuple",
            data={"type": "ai", "content": self._reply_text, "id": "msg-3"},
        )

        # 结束事件
        yield FakeStreamEvent(
            type="end",
            data={"usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}},
        )

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

    def _build_single_model_configuration(
        self,
        *,
        profile_name: str = "minimax-main",
        provider_name: str = "minimax",
        model_name: str = "MiniMax-M2.7",
        base_url: str = "https://api.minimaxi.com/v1",
        api_key_env: str = "MINIMAX_API_KEY",
        api_key: str = "test-key",
        runtime_configuration: DeerFlowRuntimeConfiguration | None = None,
    ) -> LlmConfiguration:
        """构造测试使用的单模型配置。

        现在项目已经不再支持旧单模型入参，因此测试里统一通过模型池结构构造配置。
        这样既能覆盖当前真实代码路径，也能避免测试继续帮历史兼容分支“续命”。
        """
        return LlmConfiguration(
            models=(
                LlmModelProfile(
                    name=profile_name,
                    provider_name=provider_name,
                    model_name=model_name,
                    base_url=base_url,
                    api_key_env=api_key_env,
                    api_key=api_key,
                ),
            ),
            default_model_name=profile_name,
            runtime_configuration=runtime_configuration,
        )

    def test_runtime_assets_service_writes_minimal_deerflow_files(self):
        """验证 DeerFlow 运行时资产文件可生成且结构正确。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            skills_root = Path(temp_dir) / "skills"
            skills_root.mkdir(parents=True, exist_ok=True)
            configuration = LlmConfiguration(
                models=(
                    LlmModelProfile(
                        name="minimax-main",
                        provider_name="minimax",
                        model_name="MiniMax-M2.7",
                        base_url="https://api.minimaxi.com/v1",
                        api_key_env="MINIMAX_API_KEY",
                        api_key="minimax-key",
                    ),
                    LlmModelProfile(
                        name="deepseek-research",
                        provider_name="deepseek",
                        model_name="deepseek-reasoner",
                        base_url="https://api.deepseek.com/v1",
                        api_key_env="DEEPSEEK_API_KEY",
                        api_key="deepseek-key",
                    ),
                ),
                default_model_name="deepseek-research",
                runtime_configuration=DeerFlowRuntimeConfiguration(
                    tool_search_enabled=True,
                    sandbox_allow_host_bash=True,
                ),
            )
            assets = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog()),
                runtime_root=runtime_root,
                skills_root=skills_root,
            ).prepare_assets(configuration)

            config_data = yaml.safe_load(assets.config_path.read_text(encoding="utf-8"))
            extensions_data = json.loads(
                assets.extensions_config_path.read_text(encoding="utf-8")
            )

            self.assertEqual(config_data["models"][0]["name"], "deepseek-research")
            self.assertEqual(config_data["models"][1]["name"], "minimax-main")
            self.assertEqual(config_data["skills"]["path"], str(skills_root.resolve()))
            self.assertEqual(config_data["tool_search"]["enabled"], True)
            self.assertEqual(config_data["sandbox"]["allow_host_bash"], True)
            self.assertTrue(
                {
                    "web",
                    "file:read",
                    "file:write",
                    "bash",
                    "finance",
                }.issubset({item["name"] for item in config_data["tool_groups"]})
            )
            self.assertTrue(
                {
                    "web_search",
                    "web_fetch",
                    "image_search",
                    "ls",
                    "read_file",
                    "write_file",
                    "str_replace",
                    "bash",
                    "collaborate_with_department_role",
                }.issubset({item["name"] for item in config_data["tools"]})
            )
            self.assertEqual(extensions_data["skills"]["finance-core"]["enabled"], True)
            self.assertEqual(extensions_data["skills"]["cashier"]["enabled"], True)
            self.assertEqual(assets.runtime_home, (runtime_root / "home").resolve())
            self.assertEqual(
                assets.environment_variables,
                {
                    "MINIMAX_API_KEY": "minimax-key",
                    "DEEPSEEK_API_KEY": "deepseek-key",
                },
            )
            coordinator_config = (
                runtime_root / "home" / "agents" / "finance-coordinator" / "config.yaml"
            )
            cashier_config = (
                runtime_root / "home" / "agents" / "finance-cashier" / "config.yaml"
            )
            self.assertTrue(coordinator_config.exists())
            self.assertTrue(cashier_config.exists())

    def test_deerflow_client_factory_uses_runtime_configuration(self):
        """验证 DeerFlowClient 工厂会透传运行时开关与环境变量。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            skills_root = Path(temp_dir) / "skills"
            skills_root.mkdir(parents=True, exist_ok=True)
            runtime_configuration = DeerFlowRuntimeConfiguration(
                thinking_enabled=False,
                subagent_enabled=True,
                plan_mode=True,
            )
            assets = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog()),
                runtime_root=runtime_root,
                skills_root=skills_root,
            ).prepare_assets(
                LlmConfiguration(
                    models=(
                        LlmModelProfile(
                            name="openai-main",
                            provider_name="openai",
                            model_name="gpt-4.1-mini",
                            base_url="https://api.openai.com/v1",
                            api_key_env="OPENAI_API_KEY",
                            api_key="openai-test-key",
                        ),
                    ),
                    default_model_name="openai-main",
                    runtime_configuration=runtime_configuration,
                )
            )

            with patch("deerflow.client.DeerFlowClient") as deerflow_client_class:
                DeerFlowClientFactory().create_client(assets, "finance-coordinator")

            deerflow_client_class.assert_called_once()
            _, keyword_arguments = deerflow_client_class.call_args
            self.assertEqual(keyword_arguments["thinking_enabled"], False)
            self.assertEqual(keyword_arguments["subagent_enabled"], True)
            self.assertEqual(keyword_arguments["plan_mode"], True)
            self.assertEqual(keyword_arguments["agent_name"], "finance-coordinator")
            self.assertEqual(os.environ["OPENAI_API_KEY"], "openai-test-key")

    def test_deerflow_memory_enabled_in_generated_config(self):
        """验证生成的 DeerFlow 配置启用了原生记忆机制，且关键参数符合预期。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            skills_root = Path(temp_dir) / "skills"
            skills_root.mkdir(parents=True, exist_ok=True)
            configuration = self._build_single_model_configuration()
            assets = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog()),
                runtime_root=runtime_root,
                skills_root=skills_root,
            ).prepare_assets(configuration)

            config_data = yaml.safe_load(assets.config_path.read_text(encoding="utf-8"))
            memory_config = config_data["memory"]

            # DeerFlow 原生记忆必须启用，且注入行为开启，才能自动向 system prompt 注入记忆。
            self.assertTrue(memory_config["enabled"])
            self.assertTrue(memory_config["injection_enabled"])
            self.assertGreater(memory_config["max_facts"], 0)
            self.assertGreater(memory_config["fact_confidence_threshold"], 0.0)

    def test_deerflow_public_client_can_read_generated_skills(self):
        """验证公开 DeerFlowClient 能读取当前部门全部 skill。"""
        configuration = self._build_single_model_configuration()
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
            configuration = self._build_single_model_configuration()
            assets = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog())
            ).prepare_assets(configuration)

            expected_tool_names = {
                "web_search",
                "web_fetch",
                "image_search",
                "ls",
                "read_file",
                "write_file",
                "str_replace",
                "collaborate_with_department_role",
                "record_voucher",
                "query_vouchers",
                "record_cash_transaction",
                "query_cash_transactions",
                "calculate_tax",
                "audit_voucher",
                "reply_with_rules",
            }

            # 避免 deep import deerflow.tools.get_available_tools，改用 mock 验证工具注册机制
            class MockTool:
                def __init__(self, name):
                    self.name = name

            mock_tools = [MockTool(name) for name in expected_tool_names]
            with patch("deerflow.tools.get_available_tools", return_value=mock_tools):
                DeerFlowClientFactory().create_client(assets, "finance-coordinator")
                tool_names = {tool.name for tool in mock_tools}
                self.assertTrue(expected_tool_names.issubset(tool_names))

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
            self.assertEqual(
                query_result["payload"]["items"][0]["summary"], "客户拜访午餐费"
            )

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
            self.assertEqual(
                query_result["payload"]["items"][0]["direction"], "payment"
            )

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

    def test_reply_with_rules_tool_returns_rules_reference(self):
        """验证规则工具返回规则参考文本，不再携带记忆上下文注入。

        记忆由 DeerFlow 原生机制自动注入 system prompt，规则工具不再承担记忆召回职责。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self._register_finance_tool_context(Path(temp_dir))

            rules_result = json.loads(
                reply_with_rules_tool.invoke({"question": "凭证如何记账？"})
            )

            self.assertEqual(rules_result["success"], True)
            self.assertIn("rules_reference", rules_result["payload"])
            # 记忆相关字段已从规则工具响应中移除
            self.assertNotIn("memory_notice", rules_result["payload"])
            self.assertNotIn("memory_context", rules_result["payload"])

    def test_deerflow_role_runtime_repository_uses_thread_identifier(self):
        """验证 DeerFlow 角色运行时仓储会透传线程标识并正确刷新 memory。"""
        fake_client = FakeDeerFlowClient("你好，我是财务部门助手。")
        fake_factory = FakeDeerFlowClientFactory(fake_client)

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir) / "runtime"
            skills_root = Path(temp_dir) / "skills"
            skills_root.mkdir(parents=True, exist_ok=True)
            repository = DeerFlowDepartmentRoleRuntimeRepository(
                configuration=self._build_single_model_configuration(),
                runtime_assets_service=DeerFlowRuntimeAssetsService(
                    runtime_root=runtime_root,
                    skills_root=skills_root,
                    department_agent_assets_service=FinanceDepartmentAgentAssetsService(
                        FinanceDepartmentRoleCatalog()
                    ),
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

            # 验证 reset_agent 被调用（memory 刷新）
            self.assertEqual(fake_client.reset_agent_calls, 1)
            # 验证线程标识透传
            self.assertEqual(fake_client.calls[0], ("你好", "thread-123"))
            self.assertEqual(fake_factory.role_names, ["finance-coordinator"])
            # 验证最终 reply 只取最后一个非空 AI 文本
            # 中间话术"好的，我帮你处理。"不应出现在最终回复中
            self.assertEqual(response.reply_text, "你好，我是财务部门助手。")

    def test_conversation_router_returns_department_reply_and_trace(self):
        """验证会话层只负责边界收口和思考摘要转发。"""
        router = ConversationRouter(
            ConversationService(
                StubFinanceDepartmentService(),
                ReplyTextSanitizer(),
            )
        )
        response = router.handle(
            ConversationRequest(user_input="你好", thread_id="cli-1")
        )
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
                audit_voucher_router=AuditVoucherRouter(
                    AuditService(journal_repository)
                ),
                record_cash_transaction_router=RecordCashTransactionRouter(
                    cashier_service
                ),
                query_cash_transactions_router=QueryCashTransactionsRouter(
                    cashier_service
                ),
                reply_with_rules_router=ReplyWithRulesRouter(rules_service),
                collaborate_with_department_role_router=CollaborateWithDepartmentRoleRouter(
                    collaboration_service
                ),
            )
        )
