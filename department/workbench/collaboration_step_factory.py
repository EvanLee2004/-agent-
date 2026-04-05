"""协作步骤工厂。"""

from department.workbench.collaboration_step import CollaborationStep
from department.workbench.collaboration_step_type import CollaborationStepType
from department.workbench.execution_event import ExecutionEvent
from department.workbench.execution_event_type import ExecutionEventType
from department.workbench.role_trace_summary_builder import RoleTraceSummaryBuilder


# 工具名称到中文动作描述的映射（用于 TOOL_CALL / TASK_CALL 步骤）
_TOOL_CALL_SUMMARY_MAP = {
    "generate_fiscal_task_prompt": "生成财务任务 prompt",
    "task": "委托子代理任务",
    "record_voucher": "记录凭证",
    "query_vouchers": "查询凭证",
    "calculate_tax": "计算税款",
    "audit_voucher": "审核凭证",
    "record_cash_transaction": "记录资金变动",
    "query_cash_transactions": "查询资金变动",
    "reply_with_rules": "查询规则",
}

# 工具名称到中文结果摘要的映射（用于 TOOL_RESULT 步骤）
# 注意：TOOL_RESULT 展示的是"动作已完成"的结论，而非原始返回内容。
# 这确保协作摘要不暴露内部 JSON/prompt 等执行细节。
_TOOL_RESULT_SUMMARY_MAP = {
    "generate_fiscal_task_prompt": "财务任务 prompt 已生成",
    "task": "子代理任务已返回结果",
    "record_voucher": "凭证已记录",
    "query_vouchers": "凭证已查询",
    "calculate_tax": "税款已计算",
    "audit_voucher": "凭证已审核",
    "record_cash_transaction": "资金变动已记录",
    "query_cash_transactions": "资金变动已查询",
    "reply_with_rules": "规则已查询",
}


class CollaborationStepFactory:
    """从执行事件构造可展示的协作步骤。

    factory 负责将事件转换为对用户友好的协作步骤，核心原则是：
    - 不暴露原始 tool result JSON / prompt 正文
    - TOOL_CALL/TASK_CALL 展示"正在做什么"（动作描述）
    - TOOL_RESULT 展示"做了什么结论"（已完成状态），不展示原始返回内容
    """

    def __init__(self, summary_builder: RoleTraceSummaryBuilder):
        self._summary_builder = summary_builder

    def build_from_events(
        self,
        goal: str,
        execution_events: list[ExecutionEvent],
        final_reply_text: str,
    ) -> list[CollaborationStep]:
        """根据执行事件列表生成协作步骤列表。

        Args:
            goal: 本次处理的原始用户目标。
            execution_events: 仓储层收集的执行事件列表。
            final_reply_text: 最终回复文本（当没有可识别事件时的 fallback）。

        Returns:
            协作步骤列表，每个步骤对应一个可识别的执行动作。
            如果没有任何可识别事件，返回包含最终回复摘要的单步骤。
        """
        if not execution_events:
            # Fallback：没有任何可识别事件时，用最终回复文本生成单步骤
            return [
                CollaborationStep(
                    goal=goal,
                    step_type=CollaborationStepType.FINAL_REPLY,
                    tool_name="",
                    summary=self._summary_builder.build(final_reply_text),
                )
            ]

        steps = []
        for event in execution_events:
            step_type = _map_event_type(event.event_type)
            if event.event_type == ExecutionEventType.TOOL_CALL:
                # TOOL_CALL：展示"正在调用某工具"
                summary = _TOOL_CALL_SUMMARY_MAP.get(
                    event.tool_name, f"调用 {event.tool_name}"
                )
            elif event.event_type == ExecutionEventType.TASK_CALL:
                # TASK_CALL：展示"正在委托子代理"
                summary = _TOOL_CALL_SUMMARY_MAP.get(
                    event.tool_name, f"委托 {event.tool_name}"
                )
            elif event.event_type == ExecutionEventType.TOOL_RESULT:
                # TOOL_RESULT：展示"工具执行完毕"的结论，不暴露原始返回内容
                # 原始 event.summary（仓储层截断的 content）被替换为标准化中文结论
                summary = _TOOL_RESULT_SUMMARY_MAP.get(
                    event.tool_name, f"{event.tool_name} 已执行"
                )
            else:
                # FINAL_REPLY：用 RoleTraceSummaryBuilder 压缩后的最终回复文本
                summary = self._summary_builder.build(event.summary)

            steps.append(
                CollaborationStep(
                    goal=goal,
                    step_type=step_type,
                    tool_name=event.tool_name,
                    summary=summary,
                )
            )
        return steps


def _map_event_type(event_type: ExecutionEventType) -> CollaborationStepType:
    """将执行事件类型映射为协作步骤类型。"""
    if event_type == ExecutionEventType.TASK_CALL:
        return CollaborationStepType.TASK_CALL
    if event_type == ExecutionEventType.TOOL_CALL:
        return CollaborationStepType.TOOL_CALL
    if event_type == ExecutionEventType.TOOL_RESULT:
        return CollaborationStepType.TOOL_RESULT
    return CollaborationStepType.FINAL_REPLY
