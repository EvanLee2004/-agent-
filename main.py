"""财务助手 CLI"""

import asyncio

from infrastructure.ledger import init_ledger_db
from infrastructure.llm import LLMClient
from agents.accountant_agent import AccountantAgent
from providers.config import ensure_config, print_current_config


def init():
    """初始化：确保配置存在"""
    ensure_config()
    print_current_config()


async def main_async():
    init()
    init_ledger_db()

    llm_client = LLMClient.get_instance()
    agent = AccountantAgent(llm_client)

    print("=" * 50)
    print("智能会计已启动 - 记账/查询（quit 退出）")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("你: ").strip()
        except EOFError:
            break

        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        reply = await agent.handle(user_input)
        print(f"助手: {reply}\n")

    print("\n再见！")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
