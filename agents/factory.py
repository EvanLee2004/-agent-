"""Agent 装配工厂。

该模块只负责依赖装配，不再承担数据库初始化或默认科目灌入等启动副作用。
启动副作用统一由 `bootstrap.py` 负责。
"""

from agents.accountant_agent import AccountantAgent
from infrastructure.accounting_repository import (
    get_chart_of_accounts_repository,
    get_journal_repository,
)
from infrastructure.llm import LLMClient
from infrastructure.memory import get_memory_store
from infrastructure.skill_loader import SkillLoader


def build_accountant_agent() -> AccountantAgent:
    """构造默认运行时所需的 AccountantAgent 实例。"""
    llm_client = LLMClient.get_instance()
    llm_client.require_native_tool_calling()
    return AccountantAgent(
        llm_client=llm_client,
        journal_repository=get_journal_repository(),
        chart_repository=get_chart_of_accounts_repository(),
        memory_store=get_memory_store(),
        skill_loader=SkillLoader(),
    )
