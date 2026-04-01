"""财务助手 CLI

多轮对话支持：
- 维持会话上下文
- 自动上下文压缩（95% 阈值）
- 记忆持久化
"""

from dotenv import load_dotenv

load_dotenv()

from agents.manager import manager
from core.session import SessionManager, ConversationSession
from core.context import check_and_compact


def main():
    """CLI 主循环。"""
    print("财务助手已启动，输入 'quit' 退出\n")

    session_manager = SessionManager()
    session_id, messages = session_manager.get_or_create_session()
    session = ConversationSession(
        session_id=session_id,
        title="财务助手会话",
        agent_name="manager",
    )
    print(f"会话 ID: {session_id}")

    while True:
        user_input = input("你: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        # 添加用户消息到会话
        session.add_message("user", user_input)

        # 调用 Manager 处理
        reply = manager.process(user_input, session)

        # 添加助手消息到会话
        session.add_message("assistant", reply)

        # 持久化消息到数据库
        session_manager.add_message(session.session_id, "user", user_input)
        session_manager.add_message(session.session_id, "assistant", reply)

        # 检查是否需要压缩
        if check_and_compact(session, session_manager):
            print(f"[上下文已压缩，当前 token: {session.token_count}]")

        print(f"助手: {reply}\n")


if __name__ == "__main__":
    main()
