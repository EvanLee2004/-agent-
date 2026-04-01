"""异步 Agent 基类 - 所有 Agent 的父类"""

from abc import ABC, abstractmethod
import asyncio
from typing import Optional

from infrastructure.message_bus import MessageBus, Message


class AsyncAgent(ABC):
    """异步 Agent 基类

    所有 Agent 继承此类，实现 handle() 方法即可。
    Agent 之间通过 MessageBus 通信。
    """

    def __init__(self, name: str, bus: Optional[MessageBus] = None):
        """初始化 Agent

        Args:
            name: Agent 名称（全局唯一）
            bus: 消息总线实例，默认使用单例
        """
        self.name = name
        self.bus = bus or MessageBus.get_instance()
        self._queue = self.bus.register(name)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动 Agent，开始处理消息"""
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        """停止 Agent"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        """消息处理循环"""
        while self._running:
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self.handle(msg)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[{self.name}] Error handling message: {e}")

    @abstractmethod
    async def handle(self, msg: Message):
        """处理消息，子类必须实现

        Args:
            msg: 收到的消息
        """
        pass

    async def send_to(
        self,
        recipient: str,
        content: str,
        msg_type: str = "task",
        intent: str = "",
        **metadata,
    ) -> Optional[Message]:
        """发送消息给其他 Agent 并等待回复

        Args:
            recipient: 接收者名称
            content: 消息内容
            msg_type: 消息类型 (task/result/approval/rejection)
            intent: 意图标签
            **metadata: 附加元数据

        Returns:
            回复消息，或 None（超时/失败）
        """
        msg = Message(
            sender=self.name,
            recipient=recipient,
            content=content,
            msg_type=msg_type,
            intent=intent,
            metadata=metadata,
        )
        return await self.bus.send(msg)

    async def reply(
        self, original: Message, content: str, msg_type: str = "result", **metadata
    ):
        """回复消息

        Args:
            original: 原消息
            content: 回复内容
            msg_type: 回复消息类型
            **metadata: 附加元数据
        """
        await self.bus.reply(original, content, msg_type, **metadata)

    async def broadcast(
        self,
        content: str,
        recipients: list[str],
        msg_type: str = "task",
        intent: str = "",
    ):
        """广播消息给多个 Agent

        Args:
            content: 消息内容
            recipients: 接收者列表
            msg_type: 消息类型
            intent: 意图标签
        """
        msg = Message(
            sender=self.name,
            recipient="",
            content=content,
            msg_type=msg_type,
            intent=intent,
        )
        await self.bus.broadcast(msg, recipients)

    async def forward_to(self, msg: Message, recipient: str):
        """转发消息给另一个 Agent

        Args:
            msg: 原消息
            recipient: 目标 Agent
        """
        await self.bus.forward(msg, recipient)
