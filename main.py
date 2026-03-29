"""财务助手 CLI 入口"""

from agents.manager import manager

print("财务助手已启动，输入 'quit' 退出\n")

while True:
    user_input = input("你: ").strip()
    if user_input.lower() == "quit":
        break
    if not user_input:
        continue

    reply = manager.handle(user_input)
    print(f"助手: {reply}\n")
