"""消息总线 - 简洁的异步消息传递"""

import asyncio
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Message:
    """消息结构"""

    sender: str
    recipient: str
    content: str
    reply_to: Optional[str] = None


class MessageBus:
    """简单的内存消息总线"""

    _instance: Optional["MessageBus"] = None

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._pending: dict[str, asyncio.Future] = {}

    @classmethod
    def get_instance(cls) -> "MessageBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, name: str) -> asyncio.Queue:
        """注册 Agent，返回其消息队列"""
        self._queues[name] = asyncio.Queue()
        return self._queues[name]

    async def send(self, msg: Message) -> Optional[Message]:
        """发送消息并等待回复"""
        import uuid

        msg.reply_to = (
            msg.reply_to or f"{msg.sender}_{msg.recipient}_{uuid.uuid4().hex[:8]}"
        )
        future: asyncio.Future = asyncio.Future()
        self._pending[msg.reply_to] = future

        queue = self._queues.get(msg.recipient)
        if not queue:
            return None

        await queue.put(msg)
        try:
            return await asyncio.wait_for(future, timeout=60.0)
        except asyncio.TimeoutError:
            return None
        finally:
            self._pending.pop(msg.reply_to, None)

    async def reply(self, original: Message, content: str):
        """回复消息"""
        if original.reply_to in self._pending:
            reply = Message(
                sender=original.recipient, recipient=original.sender, content=content
            )
            self._pending[original.reply_to].set_result(reply)
