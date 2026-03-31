"""核心数据结构定义。

包含 Agent 系统中使用的数据结构：
- ThoughtResult: LLM 思考结果
- AuditResult: 审核结果
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ThoughtResult:
    """LLM 思考结果结构化返回。

    用于 BaseAgent.think() 方法返回结构化的 LLM 分析结果。

    Attributes:
        intent: 意图类型，accounting/review/transfer/unknown
        entities: 从任务中提取的实体字典，如 {"amount": 500, "type": "支出"}
        reasoning: LLM 的推理过程描述
        confidence: 置信度，0.0-1.0
    """

    intent: str = "unknown"
    entities: dict = field(default_factory=dict)
    reasoning: str = ""
    confidence: float = 1.0


@dataclass
class AuditResult:
    """审核结果。

    用于 Auditor.execute() 方法返回审核结果。

    Attributes:
        passed: 审核是否通过
        comments: 审核意见或反馈
        anomaly_flag: 异常级别，high/medium/low/None
        anomaly_reason: 异常原因描述
    """

    passed: bool = False
    comments: str = ""
    anomaly_flag: Optional[str] = None
    anomaly_reason: Optional[str] = None
