"""财务助手 CLI - 单智能体版本"""

import asyncio
import os

from infrastructure.ledger import init_ledger_db
from infrastructure.llm import LLMClient
from agents.accountant_agent import handle
from providers.config import ensure_config, print_current_config, load_config


def setup_llm():
    """根据配置初始化 LLM"""
    config = ensure_config()

    # 设置环境变量供 LLMClient 使用
    os.environ["LLM_API_KEY"] = config["api_key"]
    os.environ["LLM_MODEL"] = config["model"]

    # 根据 provider 设置 base_url
    if config["provider"] == "minimax":
        os.environ["LLM_BASE_URL"] = "https://api.minimax.chat/v1"
    elif config["provider"] == "deepseek":
        os.environ["LLM_BASE_URL"] = "https://api.deepseek.com/v1"

    # 重置 LLMClient 单例
    LLMClient.reset_instance()


async def main_async():
    # 初始化 LLM
    setup_llm()

    init_ledger_db()

    print("=" * 50)
    print("智能会计已启动 - 记账/查询（quit 退出）")
    print("=" * 50)
    print_current_config()
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

        reply = await handle(user_input)
        print(f"助手: {reply}\n")

    print("\n再见！")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
