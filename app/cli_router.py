"""CLI 路由入口。"""

import asyncio
from typing import Optional

from app.dependency_container import DependencyContainer
from configuration.configuration_service import ConfigurationService
from conversation.conversation_request import ConversationRequest


class CliRouter:
    """CLI 路由入口。"""

    def __init__(self, configuration_service: ConfigurationService):
        self._configuration_service = configuration_service

    def run(self) -> None:
        """运行 CLI。"""
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        """执行异步 CLI 主流程。"""
        configuration = self._configuration_service.ensure_configuration()
        dependency_container = DependencyContainer(configuration)
        dependency_container.build_application_bootstrapper().initialize()
        conversation_router = dependency_container.build_conversation_router()
        self._print_banner()
        while True:
            user_input = self._read_user_input()
            if user_input is None:
                break
            if not user_input:
                continue
            response = conversation_router.handle(ConversationRequest(user_input=user_input))
            print(f"助手: {response.reply_text}\n")
        print("\n再见！")

    def _read_user_input(self) -> Optional[str]:
        """读取用户输入。"""
        try:
            user_input = input("你: ").strip()
        except EOFError:
            return None
        if user_input.lower() == "quit":
            return None
        return user_input

    def _print_banner(self) -> None:
        """打印启动信息。"""
        print("=" * 50)
        print("智能会计已启动 - 记账 / 查账 / 税务 / 审核（quit 退出）")
        print("=" * 50 + "\n")
