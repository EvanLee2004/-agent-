"""DeerFlow 财务工具目录。"""

from runtime.deerflow.deerflow_tool_spec import BASH_TOOL_GROUP_NAME
from runtime.deerflow.deerflow_tool_spec import FILE_READ_TOOL_GROUP_NAME
from runtime.deerflow.deerflow_tool_spec import FILE_WRITE_TOOL_GROUP_NAME
from runtime.deerflow.deerflow_tool_spec import FINANCE_TOOL_GROUP_NAME
from runtime.deerflow.deerflow_tool_spec import WEB_TOOL_GROUP_NAME
from runtime.deerflow.deerflow_tool_spec import DeerFlowToolSpec


class DeerFlowToolCatalog:
    """集中维护财务部门暴露给 DeerFlow 的工具目录。

    工具导入路径一旦散落在多个配置构造函数里，目录调整时就很容易漏改。把工具清单
    收敛为目录对象，可以保证运行时配置、测试断言和未来角色扩展共享同一事实来源。
    """

    def list_specs(self) -> tuple[DeerFlowToolSpec, ...]:
        """返回全部财务工具定义。"""
        return (
            # 先声明 DeerFlow 官方默认 agent 常见的基础工具面，确保我们自定义财务角色
            # 在底层执行能力上尽量与 DeerFlow lead agent 保持一致。这样后续角色差异
            # 主要由 SOUL、skill 和财务工具使用策略体现，而不是因为底层少了文件或
            # 网络能力导致角色只能“弱化版运行”。
            DeerFlowToolSpec(
                "web_search",
                WEB_TOOL_GROUP_NAME,
                "deerflow.community.ddg_search.tools:web_search_tool",
            ),
            DeerFlowToolSpec(
                "web_fetch",
                WEB_TOOL_GROUP_NAME,
                "deerflow.community.jina_ai.tools:web_fetch_tool",
            ),
            DeerFlowToolSpec(
                "image_search",
                WEB_TOOL_GROUP_NAME,
                "deerflow.community.image_search.tools:image_search_tool",
            ),
            DeerFlowToolSpec(
                "ls",
                FILE_READ_TOOL_GROUP_NAME,
                "deerflow.sandbox.tools:ls_tool",
            ),
            DeerFlowToolSpec(
                "read_file",
                FILE_READ_TOOL_GROUP_NAME,
                "deerflow.sandbox.tools:read_file_tool",
            ),
            DeerFlowToolSpec(
                "write_file",
                FILE_WRITE_TOOL_GROUP_NAME,
                "deerflow.sandbox.tools:write_file_tool",
            ),
            DeerFlowToolSpec(
                "str_replace",
                FILE_WRITE_TOOL_GROUP_NAME,
                "deerflow.sandbox.tools:str_replace_tool",
            ),
            DeerFlowToolSpec(
                "bash",
                BASH_TOOL_GROUP_NAME,
                "deerflow.sandbox.tools:bash_tool",
            ),
            DeerFlowToolSpec(
                "record_voucher",
                FINANCE_TOOL_GROUP_NAME,
                "accounting.record_voucher_tool:record_voucher_tool",
            ),
            DeerFlowToolSpec(
                "query_vouchers",
                FINANCE_TOOL_GROUP_NAME,
                "accounting.query_vouchers_tool:query_vouchers_tool",
            ),
            DeerFlowToolSpec(
                "record_cash_transaction",
                FINANCE_TOOL_GROUP_NAME,
                "cashier.record_cash_transaction_tool:record_cash_transaction_tool",
            ),
            DeerFlowToolSpec(
                "query_cash_transactions",
                FINANCE_TOOL_GROUP_NAME,
                "cashier.query_cash_transactions_tool:query_cash_transactions_tool",
            ),
            DeerFlowToolSpec(
                "calculate_tax",
                FINANCE_TOOL_GROUP_NAME,
                "tax.calculate_tax_tool:calculate_tax_tool",
            ),
            DeerFlowToolSpec(
                "audit_voucher",
                FINANCE_TOOL_GROUP_NAME,
                "audit.audit_voucher_tool:audit_voucher_tool",
            ),
            DeerFlowToolSpec(
                "reply_with_rules",
                FINANCE_TOOL_GROUP_NAME,
                "rules.reply_with_rules_tool:reply_with_rules_tool",
            ),
            DeerFlowToolSpec(
                "generate_fiscal_task_prompt",
                FINANCE_TOOL_GROUP_NAME,
                "department.collaboration.generate_fiscal_task_prompt_tool:generate_fiscal_task_prompt_tool",
            ),
        )
