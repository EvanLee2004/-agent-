"""核心数据结构定义。

包含 Agent 系统中使用的数据结构：
- AuditResult: 审核结果
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AuditResult:
    """审核结果。

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
