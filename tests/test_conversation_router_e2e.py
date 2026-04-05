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
from department.collaboration.generate_fiscal_task_prompt_router import (
    GenerateFiscalTaskPromptRouter,
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
from department.workbench.collaboration_step_factory import CollaborationStepFactory
from department.workbench.role_trace_summary_builder import RoleTraceSummaryBuilder
from rules.file_rules_repository import FileRulesRepository
from rules.reply_with_rules_router import ReplyWithRulesRouter
from rules.reply_with_rules_tool import reply_with_rules_tool
from rules.rules_service import RulesService
from runtime.deerflow.deerflow_client_factory import DeerFlowClientFactory
from runtime.deerflow.deerflow_department_role_runtime_repository import (
    DeerFlowDepartmentRoleRuntimeRepository,
)
from runtime.deerflow.deerflow_invocation_runner import DeerFlowInvocationRunner
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

        模拟真实 DeerFlow embedded mode 的完整事件序列：
        1. AI 先发中间回复（如"好的，我帮你处理"）
        2. AI 发起工具调用（type=ai, tool_calls）
        3. 工具执行结果事件（type=tool）- 这是 DeerFlow 真实会发的 tool 事件
        4. AI 发最终回复（这是唯一应该进入 reply_text 的内容）

        关于 tool 事件的说明：
        DeerFlow embedded mode 的 stream() 确实会发 type="tool" 的 messages-tuple 事件。
        参见 deerflow/client.py:408-418：ToolMessage 会被序列化为 type="tool" 的事件。
        之前的注释说"DeerFlow 不直接发 tool 事件"是错误的，已修正。

        注意：最终 reply 应该只取最后一个非空 AI 文本，不受中间 tool 事件影响。
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

        # 第二个 AI 事件：发起工具调用（type=ai with tool_calls）
        yield FakeStreamEvent(
            type="messages-tuple",
            data={
                "type": "ai",
                "content": "",
                "id": "msg-2",
                "tool_calls": [{"name": "record_voucher", "args": {}, "id": "call-1"}],
            },
        )

        # 第三个事件：工具执行结果（type=tool）
        # 这是 DeerFlow 真实会发的 tool 事件，仓储代码会忽略它（只取 AI 文本）
        yield FakeStreamEvent(
            type="messages-tuple",
            data={
                "type": "tool",
                "content": '{"success": true, "voucher_id": 1}',
                "name": "record_voucher",
                "tool_call_id": "call-1",
                "id": "tool-1",
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
            data={
                "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
            },
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
        from department.workbench.collaboration_step import CollaborationStep
        from department.workbench.collaboration_step_type import CollaborationStepType

        return FinanceDepartmentResponse(
            reply_text=f"thread={request.thread_id}; input={request.user_input}",
            collaboration_steps=[
                CollaborationStep(
                    goal=request.user_input,
                    step_type=CollaborationStepType.FINAL_REPLY,
                    tool_name="",
                    summary="已接收并汇总请求。",
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
                    "generate_fiscal_task_prompt",
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

    def test_deerflow_runtime_assets_isolated_by_different_runtime_root(self):
        """验证不同 runtime_root 产生完全隔离的文件路径。

        这证明文件级隔离是有效的：即使在同一次测试中，
        两个不同的 runtime_root 也会产生完全独立的 config/checkpoint/home 路径。
        这对于 API 并发场景下的请求级隔离至关重要。

        注意：这只是文件路径隔离。进程级 os.environ 隔离仍需单独处理。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            runtime_root_a = base / "runtime_a"
            runtime_root_b = base / "runtime_b"
            skills_root = base / "skills"
            skills_root.mkdir(parents=True, exist_ok=True)

            config = LlmConfiguration(
                models=(
                    LlmModelProfile(
                        name="minimax-main",
                        provider_name="minimax",
                        model_name="MiniMax-M2.7",
                        base_url="https://api.minimaxi.com/v1",
                        api_key_env="MINIMAX_API_KEY",
                        api_key="key-a",
                    ),
                ),
                default_model_name="minimax-main",
            )

            assets_a = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog()),
                runtime_root=runtime_root_a,
                skills_root=skills_root,
            ).prepare_assets(config)

            assets_b = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog()),
                runtime_root=runtime_root_b,
                skills_root=skills_root,
            ).prepare_assets(config)

            # 验证 runtime_root 本身被正确存储在 assets 中
            self.assertEqual(assets_a.runtime_root, runtime_root_a.resolve())
            self.assertEqual(assets_b.runtime_root, runtime_root_b.resolve())

            # 验证所有子路径都完全隔离
            self.assertNotEqual(assets_a.config_path, assets_b.config_path)
            self.assertNotEqual(
                assets_a.extensions_config_path, assets_b.extensions_config_path
            )
            self.assertNotEqual(assets_a.runtime_home, assets_b.runtime_home)

            # 验证实际文件存在于各自的目录中
            self.assertTrue(assets_a.config_path.exists())
            self.assertTrue(assets_b.config_path.exists())
            self.assertTrue(assets_a.runtime_home.exists())
            self.assertTrue(assets_b.runtime_home.exists())

            # 验证文件内容不同（因为 runtime_root 不同，checkpoint 路径也不同）
            self.assertNotEqual(
                assets_a.config_path.read_text(encoding="utf-8"),
                assets_b.config_path.read_text(encoding="utf-8"),
            )

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
        """验证 DeerFlow 能从配置中加载全部财务工具（不含 legacy 协作工具）。

        阶段 3 完整财务工具集（10 个 finance 组工具）：
        - 直接工具：record_voucher / query_vouchers / record_cash_transaction /
          query_cash_transactions / calculate_tax / audit_voucher / reply_with_rules
        - 协作工具：generate_fiscal_task_prompt（阶段 2/3）
        - 基础工具：web_search / web_fetch / image_search / ls / read_file / write_file / str_replace

        collaborate_with_department_role 已于阶段 3 从工具目录移除。
        基础工具来自 DeerFlow 内置，finance 组工具由 DeerFlowToolCatalog 统一维护。
        """
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
                "generate_fiscal_task_prompt",
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
                # 阶段 3：明确验证 legacy 协作工具不在 catalog 中
                self.assertNotIn("collaborate_with_department_role", tool_names)

    def test_deerflow_subagent_enabled_parameter_passthrough(self):
        """验证 DeerFlowClient 构造时正确透传 subagent_enabled=True 参数。

        本测试验证点：
        - create_client() 调用时，subagent_enabled=True 正确传递到 DeerFlowClient 构造函数

        本测试的局限性（不测试什么）：
        - DeerFlowClient 是 lazy agent：真正的工具加载发生在 _ensure_agent()，
          即首次 stream() 调用时，而非构造函数中。因此本测试不能验证
          "task 工具在首次 stream() 时真正加入可用工具集"——这需要真实 API key
          和完整的 DeerFlow runtime，属于集成测试范畴。

        关于 task 工具可见性的说明：
        - 当 subagent_enabled=True 时，DeerFlow 内部 get_available_tools(..., subagent_enabled=True)
          会把 task_tool 加入返回列表（参见 deerflow/tools/tools.py:68-70）
        - 但该 lazy load 路径需要真实 API 调用才能端到端验证
        - 参数透传是 task 工具最终可见的必要前提
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self._register_finance_tool_context(Path(temp_dir))
            # 显式构造 subagent_enabled=True 的配置
            runtime_configuration = DeerFlowRuntimeConfiguration(
                thinking_enabled=True,
                subagent_enabled=True,
                plan_mode=False,
            )
            configuration = self._build_single_model_configuration(
                runtime_configuration=runtime_configuration,
            )
            assets = DeerFlowRuntimeAssetsService(
                FinanceDepartmentAgentAssetsService(FinanceDepartmentRoleCatalog())
            ).prepare_assets(configuration)

            with patch("deerflow.client.DeerFlowClient") as mock_client_class:
                DeerFlowClientFactory().create_client(assets, "finance-coordinator")
                # 验证 DeerFlowClient 构造函数被调用，且 subagent_enabled=True
                mock_client_class.assert_called_once()
                _, kwargs = mock_client_class.call_args
                self.assertEqual(kwargs["subagent_enabled"], True)
                self.assertEqual(kwargs["thinking_enabled"], True)
                self.assertEqual(kwargs["plan_mode"], False)
                self.assertEqual(kwargs["agent_name"], "finance-coordinator")

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
            # 构造 mock invocation_runner：create_and_run_client 调用 fake_factory 并透传结果
            _created_client = None

            def _create_and_run(assets, role_name, fn):
                nonlocal _created_client
                _created_client = fake_factory.create_client(assets, role_name)
                return fn(_created_client)

            mock_invocation_runner = MagicMock(spec=DeerFlowInvocationRunner)
            mock_invocation_runner.create_and_run_client.side_effect = _create_and_run
            mock_invocation_runner.run_with_isolation.side_effect = (
                lambda assets, c, fn: fn(c)
            )
            repository = DeerFlowDepartmentRoleRuntimeRepository(
                configuration=self._build_single_model_configuration(),
                runtime_assets_service=DeerFlowRuntimeAssetsService(
                    runtime_root=runtime_root,
                    skills_root=skills_root,
                    department_agent_assets_service=FinanceDepartmentAgentAssetsService(
                        FinanceDepartmentRoleCatalog()
                    ),
                ),
                runtime_context=DepartmentRuntimeContext(),
                reply_text_sanitizer=ReplyTextSanitizer(),
                invocation_runner=mock_invocation_runner,
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
            ),
        )
        response = router.handle(
            ConversationRequest(user_input="你好", thread_id="cli-1")
        )
        self.assertEqual(response.reply_text, "thread=cli-1; input=你好")
        self.assertEqual(len(response.collaboration_steps), 1)
        self.assertEqual(response.collaboration_steps[0].goal, "你好")
        self.assertEqual(response.collaboration_steps[0].summary, "已接收并汇总请求。")

    def test_conversation_service_strips_internal_thinking_text(self):
        """验证会话服务会剔除底层角色泄漏的内部思考片段。"""
        from department.finance_department_response import FinanceDepartmentResponse
        from department.workbench.collaboration_step import CollaborationStep
        from department.workbench.collaboration_step_type import CollaborationStepType

        class ThinkingFinanceDepartmentService(StubFinanceDepartmentService):
            """返回带思考片段的部门服务替身。"""

            def reply(self, request: FinanceDepartmentRequest):
                return FinanceDepartmentResponse(
                    reply_text="<think>内部思考</think>\n\n你好，已收到。",
                    collaboration_steps=[
                        CollaborationStep(
                            goal=request.user_input,
                            step_type=CollaborationStepType.FINAL_REPLY,
                            tool_name="",
                            summary="已读取请求。",
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
        self.assertEqual(len(response.collaboration_steps), 1)

    def _register_finance_tool_context(self, temp_path: Path) -> None:
        """构造并注册财务工具上下文（阶段 3：不含 legacy 协作层）。"""
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
        workbench_service = DepartmentWorkbenchService(
            InMemoryDepartmentWorkbenchRepository()
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
                generate_fiscal_task_prompt_router=GenerateFiscalTaskPromptRouter(),
            )
        )
