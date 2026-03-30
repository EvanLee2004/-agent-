"""数据结构定义"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ThoughtResult:
    """LLM 思考结果结构化返回"""

    intent: str = "unknown"
    entities: dict = field(default_factory=dict)
    reasoning: str = ""
    confidence: float = 1.0


@dataclass
class AuditResult:
    """审核结果"""

    passed: bool = False
    comments: str = ""
    anomaly_flag: Optional[str] = None
    anomaly_reason: Optional[str] = None
