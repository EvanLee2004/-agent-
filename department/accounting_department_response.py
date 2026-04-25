"""会计部门响应模型。"""

from dataclasses import dataclass, field

from conversation.tool_router_response import ToolRouterResponse
from department.workbench.collaboration_step import CollaborationStep


@dataclass(frozen=True)
class AccountingDepartmentResponse:
    """会计部门对外响应。"""

    reply_text: str
    collaboration_steps: list[CollaborationStep] = field(default_factory=list)
    tool_results: list[ToolRouterResponse] = field(default_factory=list)
    context_refs: list[str] = field(default_factory=list)
