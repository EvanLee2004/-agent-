"""幂等跟踪器测试。"""

import unittest

from conversation.tool_router_response import ToolRouterResponse
from runtime.deerflow.idempotency_tracker import (
    check_idempotency,
    compute_idempotency_key,
    record_idempotency,
)


class TestIdempotencyTracker(unittest.TestCase):
    """验证幂等跟踪器的会话级保护机制。"""

    def test_compute_idempotency_key_deterministic(self):
        """验证相同参数产生相同的 key。"""
        args = {"amount": 1000, "account": "银行转账"}
        key1 = compute_idempotency_key("thread-1", "record_voucher", args)
        key2 = compute_idempotency_key("thread-1", "record_voucher", args)
        self.assertEqual(key1, key2)

    def test_compute_idempotency_key_different_threads(self):
        """验证不同 thread_id 产生不同的 key。"""
        args = {"amount": 1000, "account": "银行转账"}
        key1 = compute_idempotency_key("thread-1", "record_voucher", args)
        key2 = compute_idempotency_key("thread-2", "record_voucher", args)
        self.assertNotEqual(key1, key2)

    def test_compute_idempotency_key_different_tools(self):
        """验证不同工具名称产生不同的 key。"""
        args = {"amount": 1000}
        key1 = compute_idempotency_key("thread-1", "record_voucher", args)
        key2 = compute_idempotency_key("thread-1", "record_cash_transaction", args)
        self.assertNotEqual(key1, key2)

    def test_compute_idempotency_key_different_args(self):
        """验证不同参数产生不同的 key。"""
        key1 = compute_idempotency_key("thread-1", "record_voucher", {"amount": 100})
        key2 = compute_idempotency_key("thread-1", "record_voucher", {"amount": 200})
        self.assertNotEqual(key1, key2)

    def test_record_and_check_idempotency(self):
        """验证记录后可以正确查找到缓存。"""
        key = compute_idempotency_key("thread-1", "record_voucher", {"amount": 100})
        response = ToolRouterResponse(tool_name="record_voucher", success=True, payload={"result": "已记录"})

        # 缓存中不存在
        self.assertIsNone(check_idempotency(key))

        # 记录后可以查到
        record_idempotency(key, response)
        cached = check_idempotency(key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.tool_name, "record_voucher")
        self.assertTrue(cached.success)

    def test_idempotency_key_format(self):
        """验证 key 格式包含 thread_id、tool_name 和 hash。"""
        key = compute_idempotency_key("my-thread", "my_tool", {"a": 1})
        # 格式：thread_id:tool_name:hash
        self.assertTrue(key.startswith("my-thread:my_tool:"))
        self.assertEqual(len(key.split(":")), 3)


if __name__ == "__main__":
    unittest.main()
