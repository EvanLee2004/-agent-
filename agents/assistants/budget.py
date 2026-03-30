"""预算助手"""

from agents.assistant import Assistant


class BudgetAssistant(Assistant):
    """预算助手，继承自 Assistant"""

    SYSTEM_PROMPT = "你是预算专员，负责制定和审核预算计划"


budget_assistant = BudgetAssistant()
