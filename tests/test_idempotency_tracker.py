"""crewAI 会计工具幂等测试。"""

import unittest

from conversation.tool_router_response import ToolRouterResponse
from runtime.crewai.idempotency_tracker import (
    check_idempotency,
    clear_idempotency,
    compute_idempotency_key,
    record_idempotency,
)


class CrewAIIdempotencyTrackerTest(unittest.TestCase):
    """验证写工具幂等 key 的稳定性和线程隔离。"""

    def setUp(self):
        clear_idempotency()

    def tearDown(self):
        clear_idempotency()

    def test_same_arguments_with_different_order_share_key(self):
        """字典字段顺序不同不应导致重复记账。"""
        left = compute_idempotency_key(
            "thread-a",
            "record_voucher",
            {"summary": "收入", "amount": 100},
        )
        right = compute_idempotency_key(
            "thread-a",
            "record_voucher",
            {"amount": 100, "summary": "收入"},
        )

        self.assertEqual(left, right)

    def test_thread_id_is_part_of_key(self):
        """不同会话线程不能共享写工具幂等结果。"""
        left = compute_idempotency_key("thread-a", "record_voucher", {"amount": 100})
        right = compute_idempotency_key("thread-b", "record_voucher", {"amount": 100})

        self.assertNotEqual(left, right)

    def test_record_and_check_response(self):
        """幂等缓存返回原始工具响应。"""
        key = compute_idempotency_key("thread-a", "record_voucher", {"amount": 100})
        response = ToolRouterResponse(
            tool_name="record_voucher",
            success=True,
            payload={"voucher_id": 1},
        )

        record_idempotency(key, response)

        self.assertEqual(check_idempotency(key), response)


if __name__ == "__main__":
    unittest.main()
