"""DeerFlow 工具调用幂等跟踪器。

为 DeerFlow 工具调用提供会话级幂等保护：同一会话中相同工具的相同参数
不会被重复执行。这保护系统免受 DeerFlow 自动重试导致的双重写操作。

幂等 key 格式：{thread_id}:{tool_name}:{args_hash}
"""

import hashlib
import json

from conversation.tool_router_response import ToolRouterResponse


# 模块级幂等缓存：{idempotency_key -> cached_response}
# 在 DeerFlow 工具重试场景下，同一工具调用的参数通常完全相同，
# 通过 args hash 检测重复。
_idempotency_cache: dict[str, ToolRouterResponse] = {}


def _normalize_args(args: dict) -> str:
    """将工具参数规范化为 JSON 字符串（保证不同 Python dict 构造方式产生相同结果）。"""
    return json.dumps(args, sort_keys=True, ensure_ascii=True)


def compute_idempotency_key(
    thread_id: str,
    tool_name: str,
    args: dict,
) -> str:
    """计算幂等 key。

    Args:
        thread_id: 线程标识。
        tool_name: 工具名称。
        args: 工具参数字典。

    Returns:
        幂等 key，格式为 {thread_id}:{tool_name}:{args_hash}
    """
    args_hash = hashlib.sha256(_normalize_args(args).encode()).hexdigest()[:16]
    key_prefix = thread_id + ":" + tool_name + ":"
    return key_prefix + args_hash


def check_idempotency(key: str) -> ToolRouterResponse | None:
    """检查幂等缓存。

    Args:
        key: 幂等 key。

    Returns:
        如果 key 已存在，返回缓存的响应；否则返回 None。
    """
    return _idempotency_cache.get(key)


def record_idempotency(key: str, response: ToolRouterResponse) -> None:
    """记录幂等响应。

    Args:
        key: 幂等 key。
        response: 工具路由响应。
    """
    _idempotency_cache[key] = response
