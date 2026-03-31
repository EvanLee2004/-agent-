"""审核 Agent，负责审查记账结果。

Auditor 是审核记账的 Agent：
1. 用 think() 分析记账结果
2. 用 execute() 执行审核，检查是否符合规则
3. 返回审核结果
"""

import json
from typing import Optional

from agents.base import BaseAgent
from core.schemas import AuditResult, ThoughtResult


class Auditor(BaseAgent):
    """审核 Agent。

    职责：
    - 审查会计的记账结果是否符合规则
    - 发现问题时标注，让会计主动修改
    - 返回结构化的审核结果

    Attributes:
        NAME: Agent 名称
        SYSTEM_PROMPT: 系统提示词
    """

    NAME = "auditor"
    SYSTEM_PROMPT = (
        "你是财务审核，负责审查会计的记账结果是否符合规则。"
        "发现问题时要标注，让会计主动修改，不要直接打回。"
    )

    def process(self, task: str) -> str:
        """处理审核任务。

        如果直接调用 process()，会走完整的流程。

        Args:
            task: 待审核的记账结果

        Returns:
            审核结果字符串
        """
        thought = self.think(task)
        result = self._audit(thought, {})
        if result.passed:
            return "审核通过"
        return result.comments

    def execute(self, plan: ThoughtResult, context: dict) -> str:
        """执行审核（对外接口）。

        根据 plan 和 context 中的记账记录进行审核。
        返回审核结果的字符串形式。

        Args:
            plan: think() 返回的结构化思考结果
            context: 额外上下文

        Returns:
            审核结果字符串
        """
        result = self._audit(plan, context)
        if result.passed:
            return "审核通过"
        return result.comments

    def _audit(self, plan: ThoughtResult, context: dict) -> AuditResult:
        """执行审核（内部方法）。

        根据 plan 和 context 中的记账记录进行审核。

        Args:
            plan: think() 返回的结构化思考结果
            context: 额外上下文

        Returns:
            AuditResult 结构化审核结果
        """
        rules = self.read_rules()
        record = context.get("record", "")

        prompt = (
            f"审查以下记账结果是否符合规则：\n{record}\n\n"
            f"规则：\n{rules}\n\n"
            "审查要求：\n"
            "1. 逐条检查是否符合规则\n"
            "2. 如发现问题，在 comments 中详细说明\n"
            "3. 如无问题，设置 passed=true\n"
            "4. 不要直接说'打回'，而是标注问题让对方主动修改\n\n"
            '返回 JSON 格式：\n{"passed": true/false, '
            '"comments": "审核意见", '
            '"anomaly_flag": "high|medium|low|null", '
            '"anomaly_reason": "原因"}'
        )

        messages = self.build_messages(prompt)
        response = self.call_llm(messages)

        return self._parse_response(response)

    def think(self, task: str, hint: str = "") -> ThoughtResult:
        """重写 think 方法，针对审核场景。

        审核场景下的 think 不做意图分类，而是分析记账结果是否有问题。

        Args:
            task: 待审核的记账结果
            hint: 额外提示

        Returns:
            ThoughtResult 结构化结果
        """
        system_hint = hint or (
            "你是一个财务审核专家。分析以下记账结果，判断是否合规。"
            "\n\n返回格式："
            "\n{"
            '\n  "intent": "audit",'
            '\n  "entities": {"record": "...", "issues": []},'
            '\n  "reasoning": "审核推理过程",'
            '\n  "confidence": 0.0-1.0'
            "}"
        )

        messages = [
            {
                "role": "system",
                "content": f"{self.SYSTEM_PROMPT}\n\n{system_hint}",
            },
            {
                "role": "user",
                "content": f"记账结果：{task}\n\n请分析并返回 JSON。",
            },
        ]

        response = self.call_llm(messages)
        return self._parse_thought(response)

    def _parse_response(self, raw: str) -> AuditResult:
        """解析 LLM 返回为 AuditResult。

        Args:
            raw: LLM 返回的原始文本

        Returns:
            解析后的 AuditResult，解析失败时返回降级结果
        """
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end != 0:
                data = json.loads(raw[start:end])
                return AuditResult(
                    passed=data.get("passed", False),
                    comments=data.get("comments", ""),
                    anomaly_flag=data.get("anomaly_flag"),
                    anomaly_reason=data.get("anomaly_reason"),
                )
        except (json.JSONDecodeError, ValueError):
            pass

        if "通过" in raw or "pass" in raw.lower():
            return AuditResult(passed=True, comments="审核通过")
        return AuditResult(passed=False, comments=raw)
