"""报表助手"""

from agents.assistant import Assistant


class ReportAssistant(Assistant):
    """报表助手，继承自 Assistant"""

    SYSTEM_PROMPT = "你是报表专员，负责生成和分析财务报表"


report_assistant = ReportAssistant()
