"""异步 Agent 基类"""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio

from core.message_bus import MessageBus, Message


class AsyncAgent(ABC):
    """异步 Agent 基类"""

    def __init__(self, name: str, bus: Optional[MessageBus] = None):
        self.name = name
        self.bus = bus or MessageBus.get_instance()
        self._queue = self.bus.register(name)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动 Agent"""
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

    @abstractmethod
    async def handle(self, msg: Message):
        """处理消息，子类实现"""
        pass

    async def send_to(self, recipient: str, content: str) -> Optional[Message]:
        """发送消息给其他 Agent"""
        msg = Message(sender=self.name, recipient=recipient, content=content)
        return await self.bus.send(msg)

    async def reply(self, original: Message, content: str):
        """回复消息"""
        await self.bus.reply(original, content)
