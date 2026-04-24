"""会计工具调用幂等跟踪器。"""

import hashlib
import json

from conversation.tool_router_response import ToolRouterResponse


_IDEMPOTENCY_CACHE: dict[str, ToolRouterResponse] = {}


def compute_idempotency_key(
    thread_id: str,
    tool_name: str,
    arguments: dict,
) -> str:
    """计算请求内幂等 key。

    crewAI 可能在同一任务中重试工具调用。记账是有副作用的写操作，因此对
    同一 thread_id、同一工具、同一参数的调用做幂等保护，避免重复入账。
    """
    normalized_arguments = json.dumps(arguments, sort_keys=True, ensure_ascii=True)
    args_hash = hashlib.sha256(normalized_arguments.encode()).hexdigest()[:16]
    return f"{thread_id}:{tool_name}:{args_hash}"


def check_idempotency(key: str) -> ToolRouterResponse | None:
    """读取幂等缓存。"""
    return _IDEMPOTENCY_CACHE.get(key)


def record_idempotency(key: str, response: ToolRouterResponse) -> None:
    """保存幂等缓存。"""
    _IDEMPOTENCY_CACHE[key] = response


def clear_idempotency() -> None:
    """清空幂等缓存。

    生产代码通常不需要主动清空：缓存 key 已经包含 thread_id，能避免跨线程重复。
    这个入口主要服务测试和本地重置场景，避免测试间共享模块级缓存导致结果互相污染。
    """
    _IDEMPOTENCY_CACHE.clear()
