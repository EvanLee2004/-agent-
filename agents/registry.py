"""意图注册中心 - 意图到处理 Agent 的动态映射。

按需调度：Receptionist 根据意图查询这里，找到对应的 Agent 直接发送。
无需中间层，加新 Agent 只需注册即可。

使用示例：
    from agents.registry import resolve_handler

    target = resolve_handler("accounting")  # 返回 "会计"
"""

from typing import Final

# 意图 → 处理 Agent 名称
INTENT_HANDLERS: Final[dict[str, str]] = {
    "accounting": "会计",
    "transfer": "会计",
    "review": "会计",
    "audit": "审计",
    "chat": "财务专员",
}


def resolve_handler(intent: str) -> str:
    """根据意图找到处理 Agent。

    Args:
        intent: 意图类型，如 accounting, transfer, review, chat

    Returns:
        处理该意图的 Agent 名称
    """
    return INTENT_HANDLERS.get(intent, "财务专员")


def register_intent(intent: str, handler: str) -> None:
    """注册新的意图处理器（运行时动态注册）。

    Args:
        intent: 意图类型
        handler: 处理该意图的 Agent 名称
    """
    INTENT_HANDLERS[intent] = handler
