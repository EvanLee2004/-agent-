"""crewAI 会计工具包装器测试。"""

import json
import unittest

from conversation.tool_router_response import ToolRouterResponse
from department.department_runtime_context import DepartmentRuntimeContext
from department.workbench.execution_event_type import ExecutionEventType
from runtime.crewai.accounting_tool_context import AccountingToolContext
from runtime.crewai.accounting_tool_context_registry import (
    AccountingToolContextRegistry,
)
from runtime.crewai.audit_voucher_tool import audit_voucher_tool
from runtime.crewai.execution_event_scope import open_execution_event_scope
from runtime.crewai.idempotency_tracker import clear_idempotency
from runtime.crewai.query_chart_of_accounts_tool import query_chart_of_accounts_tool
from runtime.crewai.query_vouchers_tool import query_vouchers_tool
from runtime.crewai.record_voucher_tool import record_voucher_tool


class FakeRouter:
    """记录参数并返回固定响应的工具路由。"""

    def __init__(self, tool_name: str, payload: dict):
        self.tool_name = tool_name
        self.payload = payload
        self.calls = []

    def route(self, arguments: dict) -> ToolRouterResponse:
        """记录调用参数。"""
        self.calls.append(arguments)
        return ToolRouterResponse(
            tool_name=self.tool_name,
            success=True,
            payload=self.payload,
        )


def _build_context() -> AccountingToolContext:
    """构造工具包装器测试上下文。"""
    return AccountingToolContext(
        record_voucher_router=FakeRouter("record_voucher", {"voucher_id": 1}),
        query_vouchers_router=FakeRouter("query_vouchers", {"count": 0, "items": []}),
        audit_voucher_router=FakeRouter(
            "audit_voucher",
            {"audited_voucher_ids": [1], "summary": "审核完成"},
        ),
        query_chart_of_accounts_router=FakeRouter(
            "query_chart_of_accounts",
            {"count": 1, "items": [{"code": "1001", "name": "库存现金"}]},
        ),
    )


class CrewAIAccountingToolTest(unittest.TestCase):
    """验证 crewAI 工具包装器到业务路由的映射。"""

    def setUp(self):
        clear_idempotency()

    def tearDown(self):
        clear_idempotency()

    def test_record_voucher_maps_arguments_and_records_events(self):
        """记账工具应调用业务路由并记录工具事件。"""
        context = _build_context()
        runtime_context = DepartmentRuntimeContext()

        with runtime_context.open_scope("thread-1"):
            with AccountingToolContextRegistry.open_context_scope(context):
                with open_execution_event_scope() as events:
                    result_text = record_voucher_tool._run(
                        voucher_date="2024-03-01",
                        summary="销售收入",
                        source_text="收到客户货款",
                        lines=[
                            {
                                "subject_code": "1002",
                                "subject_name": "银行存款",
                                "debit_amount": 100,
                                "credit_amount": 0,
                            },
                            {
                                "subject_code": "5001",
                                "subject_name": "主营业务收入",
                                "debit_amount": 0,
                                "credit_amount": 100,
                            },
                        ],
                    )

        result = json.loads(result_text)
        self.assertTrue(result["success"])
        self.assertEqual(result["payload"]["voucher_id"], 1)
        self.assertEqual(len(context.record_voucher_router.calls), 1)
        self.assertEqual(
            [event.event_type for event in events],
            [ExecutionEventType.TOOL_CALL, ExecutionEventType.TOOL_RESULT],
        )

    def test_record_voucher_is_idempotent_in_same_thread(self):
        """同线程相同记账参数不会重复调用写路由。"""
        context = _build_context()
        runtime_context = DepartmentRuntimeContext()
        arguments = {
            "voucher_date": "2024-03-01",
            "summary": "销售收入",
            "source_text": "",
            "lines": [
                {
                    "subject_code": "1002",
                    "subject_name": "银行存款",
                    "debit_amount": 100,
                    "credit_amount": 0,
                },
                {
                    "subject_code": "5001",
                    "subject_name": "主营业务收入",
                    "debit_amount": 0,
                    "credit_amount": 100,
                },
            ],
        }

        with runtime_context.open_scope("thread-1"):
            with AccountingToolContextRegistry.open_context_scope(context):
                with open_execution_event_scope():
                    record_voucher_tool._run(**arguments)
                    record_voucher_tool._run(**arguments)

        self.assertEqual(len(context.record_voucher_router.calls), 1)

    def test_query_and_audit_tools_route_to_expected_router(self):
        """查账、审核、科目查询工具都只做轻量映射。"""
        context = _build_context()

        with AccountingToolContextRegistry.open_context_scope(context):
            with open_execution_event_scope():
                query_vouchers_tool._run(limit=5, status="pending")
                audit_voucher_tool._run(target="voucher_id", voucher_id=1)
                query_chart_of_accounts_tool._run()

        self.assertEqual(context.query_vouchers_router.calls[0]["limit"], 5)
        self.assertEqual(context.audit_voucher_router.calls[0]["voucher_id"], 1)
        self.assertEqual(context.query_chart_of_accounts_router.calls[0], {})


if __name__ == "__main__":
    unittest.main()
