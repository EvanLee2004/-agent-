"""AccountantAgent 原生 function calling 端到端测试。

测试目标覆盖两类事情：
1. 核心业务主路径在原生工具调用模式下仍然可用
2. 本轮架构重构后的关键约束被测试锁住

关键约束包括：
- Agent 构造函数本身不再初始化数据库
- 第一轮必须通过工具执行真实动作，而不是退回自由聊天
- 记账、查账、税务、审核、记忆、规则问答都走同一套 tool runtime
"""

import tempfile
import unittest
from pathlib import Path
from typing import Any, Optional

from agents.accountant_agent import AccountantAgent
from bootstrap import ApplicationBootstrapper
from domain.tax import TaxRequest, TaxType, TaxpayerType
from domain.models import VoucherDraft, VoucherLineDraft
from infrastructure.accounting_repository import (
    SQLiteChartOfAccountsRepository,
    SQLiteJournalRepository,
)
from infrastructure.llm import LLMResponse, LLMToolCall
from infrastructure.memory import OpenClawMemoryStore
from infrastructure.memory_index import SQLiteMemoryIndex
from infrastructure.ledger_repository import SQLiteLedgerRepository
from infrastructure.skill_loader import SkillLoader


def build_tool_response(
    tool_name: str,
    arguments: dict[str, Any],
    call_id: Optional[str] = None,
    content: str = "",
) -> dict[str, Any]:
    """构造测试桩使用的工具调用响应。"""
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


class StubLLMClient:
    """按顺序返回预设工具响应的测试桩。"""

    def __init__(self, responses: list[Any]):
        self._responses = responses
        self.calls: list[dict[str, Any]] = []
        self.supports_native_tool_calling = True

    def require_native_tool_calling(self) -> None:
        """模拟真实 LLMClient 的能力检查接口。"""

    def chat(self, messages, temperature=0.3, max_retries=3, timeout=30):
        """保留普通 chat 兼容入口。"""
        del temperature, max_retries, timeout
        self.calls.append(
            {
                "mode": "chat",
                "messages": messages,
            }
        )
        if not self._responses:
            return LLMResponse(
                content="",
                usage={},
                model="stub",
                success=False,
                error_message="No more stub responses",
            )

        response = self._responses.pop(0)
        if isinstance(response, str):
            return LLMResponse(
                content=response,
                usage={},
                model="stub",
                success=True,
                assistant_message={"role": "assistant", "content": response},
            )

        return LLMResponse(
            content=str(response.get("content", "")),
            usage={},
            model="stub",
            success=response.get("success", True),
            error_message=response.get("error_message"),
            assistant_message={"role": "assistant", "content": str(response.get("content", ""))},
        )

    def chat_with_tools(
        self,
        messages,
        tools,
        tool_choice="auto",
        temperature=0.3,
        max_retries=3,
        timeout=30,
    ):
        """模拟原生 function calling。"""
        del temperature, max_retries, timeout
        self.calls.append(
            {
                "mode": "chat_with_tools",
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )
        if not self._responses:
            return LLMResponse(
                content="",
                usage={},
                model="stub",
                success=False,
                error_message="No more stub responses",
            )

        response = self._responses.pop(0)
        if isinstance(response, str):
            return LLMResponse(
                content=response,
                usage={},
                model="stub",
                success=True,
                assistant_message={"role": "assistant", "content": response},
            )

        if response.get("success", True) is False:
            return LLMResponse(
                content=str(response.get("content", "")),
                usage={},
                model="stub",
                success=False,
                error_message=response.get("error_message", "Stub failure"),
            )

        tool_calls: list[LLMToolCall] = []
        assistant_message = {
            "role": "assistant",
            "content": str(response.get("content", "")),
        }
        raw_tool_calls = response.get("tool_calls", [])
        if raw_tool_calls:
            assistant_message["tool_calls"] = []
            for item in raw_tool_calls:
                tool_call = LLMToolCall(
                    id=str(item["id"]),
                    name=str(item["name"]),
                    arguments=dict(item["arguments"]),
                    raw_arguments="{}",
                )
                tool_calls.append(tool_call)
                assistant_message["tool_calls"].append(
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": "{}",
                        },
                    }
                )

        return LLMResponse(
            content=str(response.get("content", "")),
            usage={},
            model="stub",
            success=True,
            tool_calls=tool_calls,
            assistant_message=assistant_message,
        )


class AccountantAgentEndToEndTest(unittest.IsolatedAsyncioTestCase):
    """AccountantAgent 端到端测试。"""

    def _build_memory_store(self, temp_path: Path) -> OpenClawMemoryStore:
        """构造测试记忆存储。"""
        index_path = temp_path / ".opencode" / "cache" / "memory_search.sqlite"
        return OpenClawMemoryStore(
            long_term_memory_file=temp_path / "MEMORY.md",
            daily_memory_dir=temp_path / "memory",
            memory_index=SQLiteMemoryIndex(index_path),
        )

    def _build_bootstrapped_agent(
        self,
        temp_path: Path,
        responses: list[Any],
    ) -> tuple[
        AccountantAgent,
        SQLiteJournalRepository,
        SQLiteLedgerRepository,
        OpenClawMemoryStore,
        StubLLMClient,
    ]:
        """构造完成 bootstrap 的 Agent。"""
        db_path = str(temp_path / "ledger.db")
        journal_repository = SQLiteJournalRepository(db_path)
        chart_repository = SQLiteChartOfAccountsRepository(db_path)
        legacy_ledger_repository = SQLiteLedgerRepository(db_path)
        ApplicationBootstrapper(
            chart_repository=chart_repository,
            journal_repository=journal_repository,
            legacy_ledger_repository=legacy_ledger_repository,
        ).initialize()

        memory_store = self._build_memory_store(temp_path)
        llm_client = StubLLMClient(responses)
        agent = AccountantAgent(
            llm_client=llm_client,
            journal_repository=journal_repository,
            chart_repository=chart_repository,
            memory_store=memory_store,
            skill_loader=SkillLoader(),
        )
        return agent, journal_repository, legacy_ledger_repository, memory_store, llm_client

    def test_agent_construction_has_no_bootstrap_side_effects(self):
        """验证 Agent 构造函数本身不再初始化数据库。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "ledger.db"
            journal_repository = SQLiteJournalRepository(str(db_path))
            chart_repository = SQLiteChartOfAccountsRepository(str(db_path))
            memory_store = self._build_memory_store(temp_path)

            AccountantAgent(
                llm_client=StubLLMClient([]),
                journal_repository=journal_repository,
                chart_repository=chart_repository,
                memory_store=memory_store,
                skill_loader=SkillLoader(),
            )

            self.assertFalse(db_path.exists())
            self.assertFalse((temp_path / "MEMORY.md").exists())

    def test_tax_request_normalizes_common_aliases(self):
        """验证税务请求会归一化常见中文别名和已观察到的拼写漂移。"""
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

    async def test_accounting_then_query_flow_uses_tool_runtime(self):
        """验证“工具记账 -> 工具查账”主流程。"""
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

            agent, journal_repository, legacy_ledger_repository, _, llm_client = (
                self._build_bootstrapped_agent(temp_path=temp_path, responses=responses)
            )

            record_result = await agent.handle("报销差旅费500元，日期2024-01-15，说明客户拜访")
            self.assertIn("记账成功", record_result)
            self.assertIn("报销客户拜访差旅费", record_result)

            vouchers = journal_repository.list_vouchers()
            self.assertEqual(len(vouchers), 1)
            self.assertEqual(vouchers[0].summary, "报销客户拜访差旅费")
            self.assertAlmostEqual(vouchers[0].total_amount, 500.0)
            self.assertEqual(legacy_ledger_repository.get(), [])

            query_result = await agent.handle("查看账目")
            self.assertIn("报销客户拜访差旅费", query_result)

            self.assertEqual(llm_client.calls[0]["tool_choice"], "required")
            self.assertEqual(llm_client.calls[1]["tool_choice"], "auto")
            self.assertEqual(llm_client.calls[2]["tool_choice"], "required")

    async def test_tax_flow_uses_calculate_tax_tool(self):
        """验证 tax 场景走原生工具调用和确定性计算。"""
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

            agent, _, _, _, _ = self._build_bootstrapped_agent(
                temp_path=temp_path,
                responses=responses,
            )
            reply = await agent.handle("小规模纳税人销售货物10000元，需要交多少增值税？")
            self.assertIn("税务计算完成：增值税", reply)
            self.assertIn("100.00元", reply)

    async def test_audit_flow_reviews_latest_voucher(self):
        """验证 audit 场景能够审核最近一张凭证。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response(
                    "audit_voucher",
                    {"target": "latest"},
                ),
                "已审核 1 张凭证，风险等级：high\n- [HIGH] LARGE_AMOUNT: 金额超过阈值。",
            ]

            agent, journal_repository, _, _, _ = self._build_bootstrapped_agent(
                temp_path=temp_path,
                responses=responses,
            )
            voucher = VoucherDraft(
                voucher_date="2024-02-01",
                summary="设备采购付款",
                lines=[
                    VoucherLineDraft(
                        subject_code="6602",
                        subject_name="管理费用",
                        debit_amount=60000,
                        credit_amount=0,
                        description="设备采购付款",
                    ),
                    VoucherLineDraft(
                        subject_code="1002",
                        subject_name="银行存款",
                        debit_amount=0,
                        credit_amount=60000,
                        description="设备采购付款",
                    ),
                ],
                source_text="支付设备采购款60000元",
            )
            voucher.apply_business_rules()
            journal_repository.create_voucher(voucher=voucher, recorded_by="测试")

            reply = await agent.handle("审核最新凭证")
            self.assertIn("风险等级：high", reply)
            self.assertIn("LARGE_AMOUNT", reply)

    async def test_memory_tools_store_and_reuse_long_term_memory(self):
        """验证显式记忆写入和复用。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response(
                    "store_memory",
                    {
                        "scope": "long_term",
                        "category": "preference",
                        "content": "用户希望报销说明默认写得简洁。",
                    },
                ),
                "我记住了：以后默认把报销说明写得简洁些。",
                build_tool_response(
                    "search_memory",
                    {
                        "query": "报销说明 简洁",
                        "limit": 5,
                    },
                ),
                "之后我会尽量把报销说明写得更简洁。",
            ]

            agent, _, _, memory_store, llm_client = self._build_bootstrapped_agent(
                temp_path=temp_path,
                responses=responses,
            )

            remember_reply = await agent.handle("记住：我以后喜欢把报销说明写得简洁一点。")
            self.assertIn("记住", remember_reply)

            long_term_memory_file = temp_path / "MEMORY.md"
            self.assertTrue(long_term_memory_file.exists())
            self.assertIn(
                "用户希望报销说明默认写得简洁。",
                long_term_memory_file.read_text(encoding="utf-8"),
            )
            search_results = memory_store.search_memories("报销说明 简洁", limit=5)
            self.assertTrue(search_results)

            second_reply = await agent.handle("以后你会怎么写报销说明？")
            self.assertIn("简洁", second_reply)
            self.assertIn(
                "用户希望报销说明默认写得简洁。",
                llm_client.calls[2]["messages"][0]["content"],
            )

    async def test_rules_questions_use_reply_with_rules_tool(self):
        """验证规则类问题也走工具链，而不是退回自由聊天。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response(
                    "reply_with_rules",
                    {"question": "报销金额超过50000元怎么办？"},
                ),
                "超过50000元的凭证需要审核。",
            ]

            agent, _, _, _, llm_client = self._build_bootstrapped_agent(
                temp_path=temp_path,
                responses=responses,
            )
            reply = await agent.handle("报销金额超过50000元怎么办？")
            self.assertIn("需要审核", reply)

            tool_names = [
                item["function"]["name"] for item in llm_client.calls[0]["tools"]
            ]
            self.assertIn("reply_with_rules", tool_names)

    async def test_final_reply_strips_think_blocks(self):
        """验证最终用户回复不会暴露 provider 的 `<think>` 内容。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response("query_vouchers", {}),
                "<think>\n先整理一下结果。\n</think>\n\n当前账目为空。",
            ]

            agent, _, _, _, _ = self._build_bootstrapped_agent(
                temp_path=temp_path,
                responses=responses,
            )
            reply = await agent.handle("查看账目")
            self.assertEqual(reply, "当前账目为空。")

    async def test_agent_rejects_free_chat_without_tool_call(self):
        """验证第一轮未触发工具时，主流程不会悄悄退回普通聊天。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = ["这是一段没有任何工具调用的直接回复"]

            agent, _, _, _, _ = self._build_bootstrapped_agent(
                temp_path=temp_path,
                responses=responses,
            )
            reply = await agent.handle("你好")
            self.assertIn("模型未调用任何工具", reply)

    async def test_full_business_flow_runs_end_to_end(self):
        """验证单个 Agent 能连续完成完整业务链路。"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            responses = [
                build_tool_response(
                    "store_memory",
                    {
                        "scope": "long_term",
                        "category": "preference",
                        "content": "用户希望报销说明默认写得简洁。",
                    },
                ),
                "我记住了：以后默认把报销说明写得简洁些。",
                build_tool_response(
                    "record_voucher",
                    {
                        "voucher_date": "2024-03-01",
                        "summary": "报销客户拜访差旅费",
                        "source_text": "报销差旅费500元，日期2024-03-01，说明客户拜访",
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
                build_tool_response(
                    "search_memory",
                    {
                        "query": "报销说明 简洁",
                        "limit": 5,
                    },
                ),
                "之后我会尽量把报销说明写得更简洁。",
                build_tool_response(
                    "reply_with_rules",
                    {"question": "超过50000元的凭证需要怎么处理？"},
                ),
                "超过50000元的凭证需要审核。",
            ]

            (
                agent,
                journal_repository,
                legacy_ledger_repository,
                memory_store,
                llm_client,
            ) = self._build_bootstrapped_agent(
                temp_path=temp_path,
                responses=responses,
            )

            remember_reply = await agent.handle("记住：我以后喜欢把报销说明写得简洁一点。")
            self.assertIn("记住", remember_reply)

            record_reply = await agent.handle("报销差旅费500元，日期2024-03-01，说明客户拜访")
            self.assertIn("记账成功", record_reply)

            query_reply = await agent.handle("查看账目")
            self.assertIn("报销客户拜访差旅费", query_reply)

            tax_reply = await agent.handle("小规模纳税人销售货物10000元，需要交多少增值税？")
            self.assertIn("100.00元", tax_reply)

            audit_reply = await agent.handle("审核最新凭证")
            self.assertIn("风险等级：low", audit_reply)

            memory_reply = await agent.handle("以后你会怎么写报销说明？")
            self.assertIn("简洁", memory_reply)

            rules_reply = await agent.handle("超过50000元的凭证需要怎么处理？")
            self.assertIn("需要审核", rules_reply)

            vouchers = journal_repository.list_vouchers()
            self.assertEqual(len(vouchers), 1)
            self.assertEqual(vouchers[0].summary, "报销客户拜访差旅费")
            self.assertEqual(legacy_ledger_repository.get(), [])
            self.assertTrue((temp_path / "MEMORY.md").exists())
            self.assertTrue(memory_store.search_memories("简洁"))

            tool_names = [
                item["function"]["name"] for item in llm_client.calls[0]["tools"]
            ]
            self.assertIn("record_voucher", tool_names)
            self.assertIn("reply_with_rules", tool_names)
