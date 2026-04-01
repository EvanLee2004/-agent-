"""默认工具处理器实现。

这里坚持两条边界：
1. handler 只负责参数校验、调用应用服务、组织结构化结果
2. 最终面向用户的自然语言回复仍由主模型生成

这样可以避免把“业务规则”和“对话措辞”重新耦合在一起。
"""

from domain.accounting import QueryRequest, VoucherDraft
from domain.audit import AuditRequest
from domain.memory import MemoryScope
from domain.tax import TaxRequest
from services.accounting_service import AccountingService
from services.audit_service import AuditService
from services.memory_service import MemoryService
from services.skill_prompt_service import SkillPromptService
from services.tax_service import TaxService
from tools.registry import ToolHandler, ToolRegistry
from tools.schemas import ToolDefinition, ToolExecutionResult


class RecordVoucherToolHandler(ToolHandler):
    """标准凭证记账工具。"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="record_voucher",
            description="把用户描述的业务交易记录为标准会计凭证，并落入主账数据库。",
            parameters={
                "type": "object",
                "properties": {
                    "voucher_date": {
                        "type": "string",
                        "description": "凭证日期，格式 YYYY-MM-DD",
                    },
                    "summary": {
                        "type": "string",
                        "description": "业务摘要，要求简洁且能表达业务实质",
                    },
                    "source_text": {
                        "type": "string",
                        "description": "原始业务描述，可选",
                    },
                    "lines": {
                        "type": "array",
                        "description": "分录行，至少两条，且借贷平衡",
                        "items": {
                            "type": "object",
                            "properties": {
                                "subject_code": {"type": "string"},
                                "subject_name": {"type": "string"},
                                "debit_amount": {"type": "number"},
                                "credit_amount": {"type": "number"},
                                "description": {"type": "string"},
                            },
                            "required": [
                                "subject_code",
                                "subject_name",
                                "debit_amount",
                                "credit_amount",
                                "description",
                            ],
                        },
                    },
                },
                "required": ["voucher_date", "summary", "lines"],
            },
        )

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def execute(self, arguments: dict) -> ToolExecutionResult:
        """执行凭证记账。"""
        try:
            voucher = VoucherDraft.from_dict(arguments)
            voucher_id = self._accounting_service.record_voucher(voucher)
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=True,
                payload={
                    "voucher_id": voucher_id,
                    "voucher_date": voucher.voucher_date,
                    "summary": voucher.summary,
                    "total_amount": voucher.total_amount,
                    "anomaly_flag": voucher.anomaly_flag,
                    "anomaly_reason": voucher.anomaly_reason,
                    "lines": [
                        {
                            "subject_code": line.subject_code,
                            "subject_name": line.subject_name,
                            "debit_amount": line.debit_amount,
                            "credit_amount": line.credit_amount,
                            "description": line.description,
                        }
                        for line in voucher.lines
                    ],
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=False,
                error_message=f"记账参数无效: {str(exc)}",
            )


class QueryVouchersToolHandler(ToolHandler):
    """凭证查询工具。"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="query_vouchers",
            description="查询已入账的凭证列表，可按日期和状态过滤。",
            parameters={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "可选日期过滤，例如 2024-03 或 2024-03-01",
                    },
                    "status": {
                        "type": "string",
                        "description": "可选状态过滤，例如 pending 或 approved",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最大返回条数，默认 20",
                    },
                },
            },
        )

    def __init__(self, accounting_service: AccountingService):
        self._accounting_service = accounting_service

    def execute(self, arguments: dict) -> ToolExecutionResult:
        """执行凭证查询。"""
        try:
            date = str(arguments.get("date", "")).strip() or None
            status = str(arguments.get("status", "")).strip() or None
            limit = int(arguments.get("limit", 20) or 20)
            entries = self._accounting_service.list_entries(
                query_request=None if not date else QueryRequest(date=date),
                status=status,
            )[:limit]
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=True,
                payload={
                    "count": len(entries),
                    "items": [
                        {
                            "voucher_id": entry.id,
                            "voucher_number": entry.voucher_number,
                            "voucher_date": entry.voucher_date,
                            "summary": entry.summary,
                            "total_amount": entry.total_amount,
                            "status": entry.status,
                            "recorded_by": entry.recorded_by,
                            "lines": [
                                {
                                    "subject_code": line.subject_code,
                                    "subject_name": line.subject_name,
                                    "debit_amount": line.debit_amount,
                                    "credit_amount": line.credit_amount,
                                    "description": line.description,
                                }
                                for line in entry.lines
                            ],
                        }
                        for entry in entries
                    ],
                },
            )
        except (TypeError, ValueError) as exc:
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=False,
                error_message=f"查账参数无效: {str(exc)}",
            )


class CalculateTaxToolHandler(ToolHandler):
    """税务计算工具。"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="calculate_tax",
            description="按中国小企业基础税规则计算税额。",
            parameters={
                "type": "object",
                "properties": {
                    "tax_type": {
                        "type": "string",
                        "enum": ["vat", "corporate_income_tax"],
                        "description": "必须严格使用 vat 或 corporate_income_tax",
                    },
                    "taxpayer_type": {
                        "type": "string",
                        "enum": [
                            "small_scale_vat_taxpayer",
                            "small_low_profit_enterprise",
                        ],
                        "description": (
                            "必须严格使用 small_scale_vat_taxpayer 或 "
                            "small_low_profit_enterprise"
                        ),
                    },
                    "amount": {"type": "number"},
                    "includes_tax": {
                        "type": "boolean",
                        "description": (
                            "仅当用户明确说“含税”或“价税合计”时填 true；"
                            "否则默认 false"
                        ),
                    },
                    "description": {"type": "string"},
                },
                "required": [
                    "tax_type",
                    "taxpayer_type",
                    "amount",
                    "includes_tax",
                ],
            },
        )

    def __init__(self, tax_service: TaxService):
        self._tax_service = tax_service

    def execute(self, arguments: dict) -> ToolExecutionResult:
        """执行税额计算。"""
        try:
            request = TaxRequest.from_dict(arguments)
            result = self._tax_service.calculate(request)
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=True,
                payload={
                    "tax_type": result.tax_type.value,
                    "taxpayer_type": result.taxpayer_type.value,
                    "taxable_base": result.taxable_base,
                    "tax_rate": result.tax_rate,
                    "payable_tax": result.payable_tax,
                    "formula": result.formula,
                    "policy_basis": result.policy_basis,
                    "notes": result.notes,
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=False,
                error_message=f"税务参数无效: {str(exc)}",
            )


class AuditVoucherToolHandler(ToolHandler):
    """凭证审核工具。"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="audit_voucher",
            description="审核最新凭证、全部凭证或指定凭证的规则风险。",
            parameters={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["latest", "all", "voucher_id"],
                    },
                    "voucher_id": {
                        "type": "integer",
                        "description": "当 target=voucher_id 时必填",
                    },
                },
                "required": ["target"],
            },
        )

    def __init__(self, audit_service: AuditService):
        self._audit_service = audit_service

    def execute(self, arguments: dict) -> ToolExecutionResult:
        """执行审核。"""
        try:
            request = AuditRequest.from_dict(arguments)
            result = self._audit_service.audit(request)
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=True,
                payload={
                    "audited_voucher_ids": result.audited_voucher_ids,
                    "risk_level": result.risk_level,
                    "summary": result.summary,
                    "suggestion": result.suggestion,
                    "flags": [
                        {
                            "code": flag.code,
                            "severity": flag.severity,
                            "message": flag.message,
                        }
                        for flag in result.flags
                    ],
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=False,
                error_message=f"审核参数无效: {str(exc)}",
            )


class StoreMemoryToolHandler(ToolHandler):
    """显式记忆写入工具。"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="store_memory",
            description="把用户明确要求记住的偏好、事实或短期上下文写入记忆。",
            parameters={
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["long_term", "daily"],
                    },
                    "category": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["scope", "category", "content"],
            },
        )

    def __init__(self, memory_service: MemoryService):
        self._memory_service = memory_service

    def execute(self, arguments: dict) -> ToolExecutionResult:
        """执行记忆写入。"""
        try:
            scope = MemoryScope(str(arguments["scope"]).strip())
            category = str(arguments["category"]).strip()
            content = str(arguments["content"]).strip()
            self._memory_service.store_memory(
                scope=scope,
                category=category,
                content=content,
            )
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=True,
                payload={
                    "stored": True,
                    "scope": scope.value,
                    "category": category,
                    "content": content,
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=False,
                error_message=f"记忆参数无效: {str(exc)}",
            )


class SearchMemoryToolHandler(ToolHandler):
    """记忆搜索工具。"""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_memory",
            description="搜索与当前问题相关的长期或每日记忆片段。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        )

    def __init__(self, memory_service: MemoryService):
        self._memory_service = memory_service

    def execute(self, arguments: dict) -> ToolExecutionResult:
        """执行记忆搜索。"""
        try:
            query = str(arguments["query"]).strip()
            limit = int(arguments.get("limit", 5) or 5)
            results = self._memory_service.search_memory(query=query, limit=limit)
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=True,
                payload={
                    "count": len(results),
                    "items": [
                        {
                            "path": item.path,
                            "scope": item.scope.value,
                            "category": item.category,
                            "content": item.content,
                            "start_line": item.start_line,
                            "end_line": item.end_line,
                            "score": item.score,
                        }
                        for item in results
                    ],
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=False,
                error_message=f"记忆搜索参数无效: {str(exc)}",
            )


class ReplyWithRulesToolHandler(ToolHandler):
    """规则参考工具。

    这个工具不是直接替用户说话，而是把当前项目的会计/报销规则整理成
    模型可继续消费的结构化参考。这样“纯问答路径”也能纳入工具运行时，
    同时不需要再起一个嵌套 LLM 调用。
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="reply_with_rules",
            description="获取项目当前的会计、报销、审核和记忆相关规则参考，用于回答规则类问题。",
            parameters={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "用户当前的问题原文",
                    },
                },
                "required": ["question"],
            },
        )

    def __init__(self, prompt_service: SkillPromptService):
        self._prompt_service = prompt_service

    def execute(self, arguments: dict) -> ToolExecutionResult:
        """返回规则参考内容。"""
        try:
            question = str(arguments["question"]).strip()
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=True,
                payload=self._prompt_service.build_rules_tool_payload(question),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return ToolExecutionResult(
                tool_name=self.definition.name,
                success=False,
                error_message=f"规则问答参数无效: {str(exc)}",
            )


def build_default_tool_registry(
    accounting_service: AccountingService,
    tax_service: TaxService,
    audit_service: AuditService,
    memory_service: MemoryService,
    prompt_service: SkillPromptService,
) -> ToolRegistry:
    """构造默认工具注册表。"""
    registry = ToolRegistry()
    registry.register(RecordVoucherToolHandler(accounting_service))
    registry.register(QueryVouchersToolHandler(accounting_service))
    registry.register(CalculateTaxToolHandler(tax_service))
    registry.register(AuditVoucherToolHandler(audit_service))
    registry.register(StoreMemoryToolHandler(memory_service))
    registry.register(SearchMemoryToolHandler(memory_service))
    registry.register(ReplyWithRulesToolHandler(prompt_service))
    return registry
