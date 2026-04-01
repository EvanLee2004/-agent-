"""消息总线 - 异步消息传递，支持灵活的消息路由"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass
class Message:
    """消息结构

    所有Agent之间通过消息总线通信。
    消息采用Request-Reply模式，支持广播。
    """

    sender: str  # 发送者名称
    recipient: str  # 接收者名称，""表示广播
    content: str  # 消息内容

    # 扩展字段
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    reply_to: Optional[str] = None  # 关联的消息ID（用于匹配回复）
    msg_type: str = "task"  # 消息类型: task/result/approval/rejection/chat
    intent: str = ""  # 意图标签: accounting/transfer/review/chat
    metadata: dict = field(default_factory=dict)  # 附加数据
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """确保元数据不为None"""
        if self.metadata is None:
            self.metadata = {}


class MessageBus:
    """异步消息总线

    支持：
    - 点对点Request-Reply通信
    - 广播消息
    - 消息持久化（可选）
    """

    _instance: Optional["MessageBus"] = None

    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}  # Agent名称 -> 消息队列
        self._pending: dict[str, asyncio.Future] = {}  # reply_to ID -> Future

    @classmethod
    def get_instance(cls) -> "MessageBus":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置实例（用于测试）"""
        cls._instance = None

    def register(self, name: str) -> asyncio.Queue:
        """注册Agent，返回其消息队列

        Args:
            name: Agent名称

        Returns:
            asyncio.Queue: 该Agent的消息队列
        """
        if name not in self._queues:
            self._queues[name] = asyncio.Queue()
        return self._queues[name]

    def unregister(self, name: str):
        """注销Agent"""
        if name in self._queues:
            del self._queues[name]

    async def send(self, msg: Message, timeout: float = 60.0) -> Optional[Message]:
        """发送消息并等待回复（Request-Reply模式）

        Args:
            msg: 要发送的消息
            timeout: 等待回复的超时时间（秒）

        Returns:
            回复消息，或None（超时/失败）
        """
        # 生成唯一reply_to ID
        if not msg.reply_to:
            msg.reply_to = f"{msg.sender}_{msg.recipient}_{msg.id}"

        # 创建Future用于接收回复
        future: asyncio.Future = MessageBus._create_future()
        self._pending[msg.reply_to] = future

        # 放入接收者队列
        queue = self._queues.get(msg.recipient)
        if not queue:
            self._pending.pop(msg.reply_to, None)
            return None

        await queue.put(msg)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self._pending.pop(msg.reply_to, None)

    async def broadcast(self, msg: Message, recipients: list[str]):
        """广播消息给多个接收者

        注意：广播不等待回复，如果需要回复用send()逐个发送

        Args:
            msg: 要广播的消息
            recipients: 接收者列表
        """
        for recipient in recipients:
            msg_copy = Message(
                sender=msg.sender,
                recipient=recipient,
                content=msg.content,
                msg_type=msg.msg_type,
                intent=msg.intent,
                metadata=msg.metadata.copy(),
            )
            queue = self._queues.get(recipient)
            if queue:
                await queue.put(msg_copy)

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
        if original.reply_to in self._pending:
            reply = Message(
                sender=original.recipient,
                recipient=original.sender,
                content=content,
                reply_to=original.id,
                msg_type=msg_type,
                intent=original.intent,
                metadata=metadata,
            )
            self._pending[original.reply_to].set_result(reply)

    async def forward(self, msg: Message, to: str):
        """转发消息给另一个Agent

        Args:
            msg: 原消息
            to: 目标Agent名称
        """
        queue = self._queues.get(to)
        if queue:
            # 创建转发消息，保持原始ID和reply_to
            forward_msg = Message(
                sender=msg.sender,
                recipient=to,
                content=msg.content,
                id=msg.id,
                reply_to=msg.reply_to,
                msg_type=msg.msg_type,
                intent=msg.intent,
                metadata=msg.metadata.copy(),
            )
            await queue.put(forward_msg)

    def get_queue(self, name: str) -> Optional[asyncio.Queue]:
        """获取Agent的消息队列"""
        return self._queues.get(name)

    @staticmethod
    def _create_future() -> asyncio.Future:
        """创建Future（兼容性封装）"""
        return asyncio.Future()
