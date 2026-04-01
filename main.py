"""财务助手 CLI - 单智能体版本"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from infrastructure.ledger import init_ledger_db
from agents.accountant_agent import handle


async def main_async():
    init_ledger_db()
    print("智能会计已启动 - 记账/查询（quit 退出）\n")

    while True:
        try:
            user_input = input("你: ").strip()
        except EOFError:
            break

        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        reply = await handle(user_input)
        print(f"助手: {reply}\n")

    print("\n再见！")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
