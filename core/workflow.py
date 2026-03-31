"""ReAct 工作流模块。

将 ReAct（Reasoning + Acting）循环逻辑从 Agent 中抽离出来，
实现工作流与业务逻辑的分离。
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from agents.base import BaseAgent
    from agents.auditor import Auditor
from core.schemas import AuditResult, ThoughtResult


class ReActWorkflow:
    """ReAct 模式工作流。

    封装了 ReAct 循环的核心逻辑：
    1. think - LLM 分析任务
    2. execute - Agent 执行动作
    3. (如果需要) audit - Auditor 审核
    4. (如果有问题) reflect - Agent 反思修正
    5. 循环直到通过或达到最大轮数

    Attributes:
        agent: 执行任务的 Agent
        auditor: 审核 Agent（可选）
        max_rounds: 最大循环轮数
    """

    def __init__(
        self,
        agent: "BaseAgent",
        auditor: Optional[Auditor] = None,
        max_rounds: int = 3,
    ):
        """初始化工作流。

        Args:
            agent: 执行任务的 Agent
            auditor: 审核 Agent（可选）
            max_rounds: 最大循环轮数，默认 3
        """
        self.agent = agent
        self.auditor = auditor
        self.max_rounds = max_rounds

    def run(self, task: str, hint: str = "") -> str:
        """运行 ReAct 工作流。

        循环执行：think → execute → (audit) → (reflect)
        直到审核通过或达到最大轮数。

        Args:
            task: 用户任务
            hint: 额外的提示信息

        Returns:
            处理结果字符串
        """
        thought = self.agent.think(task, hint)
        last_result = ""
        last_audit: AuditResult = AuditResult(passed=False, comments="")

        for _ in range(self.max_rounds):
            last_result = self.agent.execute(thought, {})

            if self.auditor:
                last_audit = self.auditor._audit(thought, {"record": last_result})

                if last_audit.passed:
                    return last_result

                self.agent.reflect(last_result, last_audit.comments)
            else:
                return last_result

        return self._format_final_result(last_result, last_audit)

    def _format_final_result(
        self,
        result: str,
        audit: AuditResult,
    ) -> str:
        """格式化最终结果。

        当达到最大轮数仍未通过审核时调用。

        Args:
            result: 最后一次执行的结果
            audit: 最后一次审核的结果

        Returns:
            格式化的结果字符串
        """
        if audit.passed:
            return result
        return (
            f"⚠️ 经过{self.max_rounds}轮讨论仍有问题，需人工确认\n\n"
            f"审核意见：{audit.comments}"
        )
