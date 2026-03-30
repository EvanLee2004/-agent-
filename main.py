"""财务助手 CLI 入口"""

from agents.manager import manager
from core.session import SessionManager


def main():
    """主函数，程序入口"""
    db = SessionManager()

    # 显示主菜单
    print("1. 新建会话  2. 历史会话  3. 退出")
    choice = input("选择: ").strip()

    if choice == "1":
        # 新建会话
        title = input("标题: ").strip() or "新会话"
        session_id = db.create(title)
        messages = []

    elif choice == "2":
        # 查看历史会话
        sessions = db.list_all()
        for i, s in enumerate(sessions, 1):
            print(f"{i}. {s['title']} ({s['updated_at'][:16]})")

        num = input("选编号: ").strip()
        if num.isdigit() and 1 <= int(num) <= len(sessions):
            session_id = sessions[int(num) - 1]["id"]
            messages = db.get(session_id)
        else:
            session_id = db.create("新会话")
            messages = []
    else:
        return

    print("财务助手已启动，输入 'quit' 退出\n")

    # 对话循环
    while True:
        user_input = input("你: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        # 保存用户消息
        messages.append({"role": "user", "content": user_input})
        db.add(session_id, "user", user_input)

        # 调用 manager 处理
        reply = manager.handle(user_input)

        # 保存助手回复
        messages.append({"role": "assistant", "content": reply})
        db.add(session_id, "assistant", reply)

        print(f"助手: {reply}\n")


if __name__ == "__main__":
    main()
