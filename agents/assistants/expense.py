"""报销助手"""

from agents.assistant import Assistant


class ExpenseAssistant(Assistant):
    SYSTEM_PROMPT = "你是报销专员，负责处理员工的报销申请"


expense_assistant = ExpenseAssistant()
