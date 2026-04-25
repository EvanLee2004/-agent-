"""会计部门会话上下文服务。"""

from conversation.tool_router_response import ToolRouterResponse
from department.conversation_context import ConversationContext
from department.workbench.department_workbench_service import DepartmentWorkbenchService


REFERENCE_HINTS = ("刚才", "上一", "上一个", "最近", "那张", "这张", "刚刚")
MAX_CONTEXT_TURNS = 3


class ConversationContextService:
    """从历史工作台生成受控上下文。

    生产级财务系统不能把 Agent 记忆当成事实来源，因此这里不让 crewAI 自行决定
    要记住什么财务事实。服务只从本项目已经落库的 workbench 历史中抽取短摘要和
    可追踪引用，再要求 Agent 涉及金额、科目、状态时必须调用工具查账确认。
    """

    def __init__(self, workbench_service: DepartmentWorkbenchService):
        self._workbench_service = workbench_service

    def build_context(self, thread_id: str, user_input: str) -> ConversationContext:
        """构造当前请求可用的历史上下文。

        Args:
            thread_id: 会话线程标识。
            user_input: 当前用户输入。

        Returns:
            可注入 crewAI prompt 的受控上下文。
        """
        turns = self._workbench_service.list_turns_with_steps(thread_id)
        if not turns:
            return ConversationContext()

        recent_turns = turns[-MAX_CONTEXT_TURNS:]
        context_refs = self._resolve_context_refs(thread_id, user_input)
        summary_lines = [
            "以下是本项目数据库中的会话摘要，只能用于理解指代，不能替代查账工具："
        ]
        for turn in recent_turns:
            summary_lines.append(
                f"- 第 {turn['turn_index']} 轮：用户={turn['original_user_input']}；"
                f"回复={turn['reply_text']}"
            )
        if context_refs:
            summary_lines.append(f"- 当前指代候选：{', '.join(context_refs)}")
        summary_lines.append(
            "- 财务事实确认规则：金额、科目、凭证状态、审核结论必须调用工具查询或审核。"
        )
        return ConversationContext(
            summary="\n".join(summary_lines),
            context_refs=context_refs,
        )

    def _resolve_context_refs(self, thread_id: str, user_input: str) -> list[str]:
        """解析“刚才那张”等上下文引用。

        当前 v1 只解析最近凭证引用。这样做保持规则可审计：指代解析只给出候选，
        后续 Agent 仍必须调用 `query_vouchers` 或 `audit_voucher` 确认事实。
        """
        if not any(hint in user_input for hint in REFERENCE_HINTS):
            return []
        latest_voucher_id = self._find_latest_voucher_id(thread_id)
        if latest_voucher_id is None:
            return []
        return [f"voucher:{latest_voucher_id}"]

    def _find_latest_voucher_id(self, thread_id: str) -> int | None:
        """从历史工具结果中寻找最近涉及的凭证 ID。"""
        events = self._workbench_service.list_execution_events_with_context(thread_id)
        for event in reversed(events):
            if event.get("event_type") != "tool_result":
                continue
            response = ToolRouterResponse.from_tool_message_content(
                str(event.get("summary") or "")
            )
            if response is None or not response.voucher_ids:
                continue
            return response.voucher_ids[-1]
        return None
