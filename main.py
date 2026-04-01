"""财务助手 CLI"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from core.ledger import init_ledger_db
from core.message_bus import MessageBus, Message
from agents.manager import Manager
from agents.accountant import Accountant
from agents.auditor import Auditor


async def main_async():
    bus = MessageBus.get_instance()

    manager = Manager(bus)
    accountant = Accountant(bus)
    auditor = Auditor(bus)

    await manager.start()
    await accountant.start()
    await auditor.start()

    init_ledger_db()
    print("财务助手已启动，输入 'quit' 退出\n")

    while True:
        user_input = input("你: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        msg = Message(sender="user", recipient="manager", content=user_input)
        reply = await bus.send(msg)

        if reply:
            print(f"助手: {reply.content}\n")
        else:
            print("助手: 请求超时\n")

    await manager.stop()
    await accountant.stop()
    await auditor.stop()


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n退出")


if __name__ == "__main__":
    main()
