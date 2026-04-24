"""请求级上下文测试。"""

import unittest
from unittest.mock import MagicMock

from department.department_error import DepartmentError
from runtime.crewai.accounting_tool_context import AccountingToolContext
from runtime.crewai.accounting_tool_context_registry import (
    AccountingToolContextRegistry,
)


class AccountingToolContextRegistryTest(unittest.TestCase):
    """验证 crewAI 工具上下文按请求隔离。"""

    def test_context_available_inside_scope(self):
        """作用域内能读取当前工具上下文。"""
        context = MagicMock(spec=AccountingToolContext)

        with AccountingToolContextRegistry.open_context_scope(context):
            self.assertIs(AccountingToolContextRegistry.get_context(), context)

    def test_context_is_cleared_after_scope(self):
        """作用域结束后不能继续读取上一次请求的上下文。"""
        context = MagicMock(spec=AccountingToolContext)

        with AccountingToolContextRegistry.open_context_scope(context):
            self.assertIs(AccountingToolContextRegistry.get_context(), context)

        with self.assertRaises(DepartmentError):
            AccountingToolContextRegistry.get_context()

    def test_nested_context_restores_previous_context(self):
        """嵌套请求作用域退出时恢复外层上下文。"""
        outer_context = MagicMock(spec=AccountingToolContext)
        inner_context = MagicMock(spec=AccountingToolContext)

        with AccountingToolContextRegistry.open_context_scope(outer_context):
            self.assertIs(AccountingToolContextRegistry.get_context(), outer_context)
            with AccountingToolContextRegistry.open_context_scope(inner_context):
                self.assertIs(AccountingToolContextRegistry.get_context(), inner_context)
            self.assertIs(AccountingToolContextRegistry.get_context(), outer_context)


if __name__ == "__main__":
    unittest.main()
