"""CLI 路由入口。"""

import asyncio
import uuid
from typing import Optional

from app.dependency_container import AppServiceFactory
from app.cli_conversation_handler import CliConversationHandler
from configuration.configuration_service import ConfigurationService
from conversation.conversation_request import ConversationRequest
from department.workbench.collaboration_step_formatter import CollaborationStepFormatter


class CliRouter:
    """CLI 路由入口。"""

    def __init__(self, configuration_service: ConfigurationService):
        self._configuration_service = configuration_service
        self._collaboration_step_formatter = CollaborationStepFormatter()

    def run(self) -> None:
        """运行 CLI。

        CLI 是最终用户直接面对的入口，因此即使用户使用 `Ctrl+C` 主动结束会话，
        也应该像普通终端产品一样安静退出，而不是把 Python 的中断栈信息直接打印出来。
        """
        try:
            self._run_event_loop()
        except KeyboardInterrupt:
            print("\n\n再见！")

    def _run_event_loop(self) -> None:
        """运行异步事件循环。

        之所以把 `asyncio.run(...)` 拆成独立方法，是为了让中断处理与测试替身更清晰，
        避免在测试中直接 patch `asyncio.run` 造成未等待协程的噪音。
        """
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        """执行异步 CLI 主流程。"""
        configuration = self._configuration_service.ensure_configuration()
        app_factory = AppServiceFactory(configuration)
        app_factory.build_application_bootstrapper().initialize()
        handler: CliConversationHandler = app_factory.build_cli_handler()
        thread_id = self._build_thread_id()
        self._print_banner()
        while True:
            user_input = self._read_user_input()
            if user_input is None:
                break
            if not user_input:
                continue
            response = handler.handle(
                ConversationRequest(
                    user_input=user_input,
                    thread_id=thread_id,
                )
            )
            collaboration_step_text = self._collaboration_step_formatter.format(response.collaboration_steps)
            if collaboration_step_text:
                print(collaboration_step_text)
            print(f"助手: {response.reply_text}\n")
        print("\n再见！")

    def _build_thread_id(self) -> str:
        """构造当前 CLI 会话的线程标识。

        Returns:
            当前进程唯一的线程 ID。
        """
        # CLI 会话内复用同一个 thread_id，才能让 DeerFlow 的检查点和上下文持续生效。
        return f"cli-{uuid.uuid4().hex}"

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
        print("智能财务部门已启动 - 对话 / 记账 / 资金 / 查账 / 税前准备 / 审核（quit 退出）")
        print("=" * 50 + "\n")
