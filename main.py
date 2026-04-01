"""财务助手 CLI - 多 Agent 协作模拟财务部门"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from infrastructure.ledger import init_ledger_db
from infrastructure.message_bus import MessageBus, Message
from agents.reception import Receptionist
from agents.accountant import Accountant
from agents.auditor import Auditor


async def main_async():
    """主异步函数"""
    # 重置消息总线（确保干净启动）
    MessageBus.reset_instance()
    bus = MessageBus.get_instance()

    # 创建并启动所有 Agent
    reception = Receptionist(bus)
    accountant = Accountant(bus)
    auditor = Auditor(bus)

    await reception.start()
    await accountant.start()
    await auditor.start()

    # 初始化数据库
    init_ledger_db()

    print("=" * 50)
    print("智能财务部门已启动")
    print("=" * 50)
    print("财务专员：您好，请问有什么可以帮您？")
    print("-" * 50)
    print("示例：")
    print("  - 报销差旅费500元，日期2024-01-15，说明客户拜访，发票已附")
    print("  - 查看账目")
    print("  - 收到货款10000元，日期2024-01-10，说明产品销售")
    print("-" * 50)
    print("输入 'quit' 退出")
    print()

    while True:
        try:
            user_input = input("你: ").strip()
        except EOFError:
            break

        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        # 用户消息通过总线发送给财务专员
        msg = Message(sender="用户", recipient="财务专员", content=user_input)
        reply = await bus.send(msg)

        if reply:
            # 根据回复类型格式化输出
            if reply.msg_type == "chat":
                print(f"助手: {reply.content}\n")
            elif reply.msg_type == "result":
                print(f"助手: {reply.content}\n")
            else:
                print(f"助手: {reply.content}\n")
        else:
            print("助手: 请求超时，请稍后重试\n")

    # 停止所有 Agent
    await reception.stop()
    await accountant.stop()
    await auditor.stop()

    print("\n再见！")


def main():
    """主入口"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\n已退出")


if __name__ == "__main__":
    main()
