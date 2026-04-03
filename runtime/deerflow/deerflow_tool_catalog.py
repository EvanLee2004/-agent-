"""DeerFlow 财务工具目录。"""

from runtime.deerflow.deerflow_tool_spec import DeerFlowToolSpec


class DeerFlowToolCatalog:
    """集中维护财务部门暴露给 DeerFlow 的工具目录。

    工具导入路径一旦散落在多个配置构造函数里，目录调整时就很容易漏改。把工具清单
    收敛为目录对象，可以保证运行时配置、测试断言和未来角色扩展共享同一事实来源。
    """

    def list_specs(self) -> tuple[DeerFlowToolSpec, ...]:
        """返回全部财务工具定义。"""
        return (
            DeerFlowToolSpec(
                "collaborate_with_department_role",
                "department.collaboration.collaborate_with_department_role_tool:collaborate_with_department_role_tool",
            ),
            DeerFlowToolSpec(
                "record_voucher",
                "accounting.record_voucher_tool:record_voucher_tool",
            ),
            DeerFlowToolSpec(
                "query_vouchers",
                "accounting.query_vouchers_tool:query_vouchers_tool",
            ),
            DeerFlowToolSpec(
                "record_cash_transaction",
                "cashier.record_cash_transaction_tool:record_cash_transaction_tool",
            ),
            DeerFlowToolSpec(
                "query_cash_transactions",
                "cashier.query_cash_transactions_tool:query_cash_transactions_tool",
            ),
            DeerFlowToolSpec(
                "calculate_tax",
                "tax.calculate_tax_tool:calculate_tax_tool",
            ),
            DeerFlowToolSpec(
                "audit_voucher",
                "audit.audit_voucher_tool:audit_voucher_tool",
            ),
            DeerFlowToolSpec(
                "store_memory",
                "memory.store_memory_tool:store_memory_tool",
            ),
            DeerFlowToolSpec(
                "search_memory",
                "memory.search_memory_tool:search_memory_tool",
            ),
            DeerFlowToolSpec(
                "reply_with_rules",
                "rules.reply_with_rules_tool:reply_with_rules_tool",
            ),
        )
