"""财务助手 CLI。"""

import asyncio

from agents.factory import build_accountant_agent
from bootstrap import bootstrap_default_application
from providers.config import ConfigValidator, ensure_config, print_current_config


def init() -> None:
    """初始化运行环境。"""
    config = ensure_config()
    validation = ConfigValidator.validate_native_tool_calling(config)
    if not validation.is_valid:
        raise RuntimeError(validation.error_message or "当前配置不支持原生 function calling")
    print_current_config()
    bootstrap_default_application()


async def main_async() -> None:
    """异步 CLI 主流程。"""
    init()
    agent = build_accountant_agent()

    print("=" * 50)
    print("智能会计已启动 - 记账 / 查账 / 税务 / 审核（quit 退出）")
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


def main() -> None:
    """CLI 入口。"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
