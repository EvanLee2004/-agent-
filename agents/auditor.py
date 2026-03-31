"""审核 Agent，负责审查记账结果。

Auditor 是审核记账的 Agent：
1. 用 LLM 理解记账结果
2. 检查是否符合规则
3. 返回审核结果
"""

import re

from agents.base import BaseAgent
from core.rules import read_rules
from core.schemas import AuditResult


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
        "你是财务审核，负责审查会计的记账结果是否符合规则。\n"
        "发现问题时要标注，让会计主动修改，不要直接打回。"
    )

    def process(self, task: str) -> str:
        """处理审核任务。

        审查记账结果，返回审核结果字符串。

        Args:
            task: 待审核的记账记录

        Returns:
            审核结果字符串
        """
        rules = read_rules()

        prompt = (
            f"审查以下记账结果是否符合规则：\n{task}\n\n"
            f"规则：\n{rules}\n\n"
            "审查要求：\n"
            "1. 逐条检查是否符合规则\n"
            "2. 如发现问题，详细说明\n"
            '3. 如无问题，说"审核通过"\n'
            "4. 不要直接说'打回'，而是标注问题让对方主动修改\n\n"
            "回答："
        )

        response = self.ask_llm(prompt)
        result = self._parse_response(response)
        if result.passed:
            return "审核通过"
        return result.comments

    def _parse_response(self, response: str) -> AuditResult:
        """从 LLM 响应中解析审核结果。

        用简单规则匹配判断是否通过。

        Args:
            response: LLM 返回的文本

        Returns:
            AuditResult 结构化审核结果
        """
        passed = False
        comments = response
        anomaly_flag = None
        anomaly_reason = None

        if "通过" in response and "不" not in response:
            passed = True
            comments = "审核通过"
        else:
            passed = False

            flag_match = re.search(r"(high|medium|low)", response.lower())
            if flag_match:
                anomaly_flag = flag_match.group(1)

            if "金额过" in response or "金额大" in response:
                anomaly_reason = "金额异常"

        return AuditResult(
            passed=passed,
            comments=comments,
            anomaly_flag=anomaly_flag,
            anomaly_reason=anomaly_reason,
        )
