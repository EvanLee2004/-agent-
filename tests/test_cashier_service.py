"""出纳服务测试。"""

import unittest
from dataclasses import dataclass
from typing import Optional

from cashier.cash_transaction import CashTransaction
from cashier.cashier_error import CashierError
from cashier.cashier_repository import CashierRepository
from cashier.cashier_service import CashierService
from cashier.query_cash_transactions_query import QueryCashTransactionsQuery
from cashier.record_cash_transaction_command import RecordCashTransactionCommand


class FakeCashierRepository(CashierRepository):
    """伪造的出纳仓储。"""

    def __init__(self):
        self._transactions: list[CashTransaction] = []
        self._next_id = 1

    @property
    def database_path(self) -> str:
        """返回底层数据库路径。"""
        return ":memory:"

    def initialize_storage(self) -> None:
        """初始化存储。"""
        pass

    def create_transaction(self, command: RecordCashTransactionCommand) -> int:
        """新增资金收付记录。"""
        transaction_id = self._next_id
        self._next_id += 1
        return transaction_id

    def list_transactions(
        self, query: QueryCashTransactionsQuery
    ) -> list[CashTransaction]:
        """查询资金收付记录。"""
        return self._transactions


class TestCashierServiceValidation(unittest.TestCase):
    """出纳服务校验规则测试。"""

    def setUp(self):
        self._repository = FakeCashierRepository()
        self._service = CashierService(self._repository)

    def test_record_transaction_with_valid_receipt(self):
        """验证有效的收款记录可以正常入账。"""
        command = RecordCashTransactionCommand(
            transaction_date="2024-03-01",
            direction="receipt",
            amount=1000.0,
            account_name="银行存款",
            summary="收到客户货款",
            counterparty="某客户",
        )
        result = self._service.record_transaction(command)
        self.assertEqual(result, 1)

    def test_record_transaction_with_valid_payment(self):
        """验证有效的付款记录可以正常入账。"""
        command = RecordCashTransactionCommand(
            transaction_date="2024-03-01",
            direction="payment",
            amount=500.0,
            account_name="银行存款",
            summary="支付供应商货款",
            counterparty="某供应商",
        )
        result = self._service.record_transaction(command)
        self.assertEqual(result, 1)

    def test_record_transaction_invalid_direction(self):
        """验证方向既不是 receipt 也不是 payment 时抛出错误。"""
        command = RecordCashTransactionCommand(
            transaction_date="2024-03-01",
            direction="transfer",
            amount=1000.0,
            account_name="银行存款",
            summary="转账",
        )
        with self.assertRaises(CashierError) as context:
            self._service.record_transaction(command)
        self.assertIn("资金方向必须为 receipt 或 payment", str(context.exception))

    def test_record_transaction_invalid_amount_zero(self):
        """验证金额为零时抛出错误。"""
        command = RecordCashTransactionCommand(
            transaction_date="2024-03-01",
            direction="receipt",
            amount=0,
            account_name="银行存款",
            summary="收到货款",
        )
        with self.assertRaises(CashierError) as context:
            self._service.record_transaction(command)
        self.assertIn("资金金额必须大于 0", str(context.exception))

    def test_record_transaction_invalid_amount_negative(self):
        """验证金额为负数时抛出错误。"""
        command = RecordCashTransactionCommand(
            transaction_date="2024-03-01",
            direction="receipt",
            amount=-100.0,
            account_name="银行存款",
            summary="收到货款",
        )
        with self.assertRaises(CashierError) as context:
            self._service.record_transaction(command)
        self.assertIn("资金金额必须大于 0", str(context.exception))

    def test_record_transaction_empty_date(self):
        """验证空日期时抛出错误。"""
        command = RecordCashTransactionCommand(
            transaction_date="",
            direction="receipt",
            amount=1000.0,
            account_name="银行存款",
            summary="收到货款",
        )
        with self.assertRaises(CashierError) as context:
            self._service.record_transaction(command)
        self.assertIn("资金日期不能为空", str(context.exception))

    def test_record_transaction_whitespace_date(self):
        """验证空白日期时抛出错误。"""
        command = RecordCashTransactionCommand(
            transaction_date="   ",
            direction="receipt",
            amount=1000.0,
            account_name="银行存款",
            summary="收到货款",
        )
        with self.assertRaises(CashierError) as context:
            self._service.record_transaction(command)
        self.assertIn("资金日期不能为空", str(context.exception))

    def test_record_transaction_empty_account_name(self):
        """验证空账户名时抛出错误。"""
        command = RecordCashTransactionCommand(
            transaction_date="2024-03-01",
            direction="receipt",
            amount=1000.0,
            account_name="",
            summary="收到货款",
        )
        with self.assertRaises(CashierError) as context:
            self._service.record_transaction(command)
        self.assertIn("资金账户不能为空", str(context.exception))

    def test_record_transaction_empty_summary(self):
        """验证空摘要时抛出错误。"""
        command = RecordCashTransactionCommand(
            transaction_date="2024-03-01",
            direction="receipt",
            amount=1000.0,
            account_name="银行存款",
            summary="",
        )
        with self.assertRaises(CashierError) as context:
            self._service.record_transaction(command)
        self.assertIn("资金摘要不能为空", str(context.exception))


class TestCashierServiceQuery(unittest.TestCase):
    """出纳服务查询测试。"""

    def setUp(self):
        self._repository = FakeCashierRepository()
        self._service = CashierService(self._repository)

    def test_query_transactions_returns_empty_list(self):
        """验证空查询返回空列表。"""
        query = QueryCashTransactionsQuery()
        result = self._service.query_transactions(query)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
