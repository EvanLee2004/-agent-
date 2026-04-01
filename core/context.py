"""上下文构建模块。

构建完整的 LLM 调用消息，结合：
- Agent 的系统提示词
- Agent 记忆（长期经验）
- 会话历史（对话上下文）
- 当前任务

处理压缩触发和执行。
"""

from typing import Optional

from core.compactor import Compactor
from core.memory import read_memory
from core.models import get_default_model
from core.session import ConversationSession, SessionManager
from core.token_counter import TokenCounter


DEFAULT_MEMORY_LIMIT = 20


def build_messages(
    system_prompt: str,
    task: str,
    session: ConversationSession,
    memory_limit: int = DEFAULT_MEMORY_LIMIT,
) -> list[dict]:
    """构建 LLM 调用所需的完整消息列表。

    通过组合以下内容构建消息：
    1. 注入记忆上下文的系统提示词
    2. 会话历史（或压缩后的摘要）
    3. 当前用户任务

    Args:
        system_prompt: Agent 的系统提示词。
        task: 当前用户任务/消息。
        session: 包含历史和 token 追踪的会话对象。
        memory_limit: 包含的记忆条目最大数量。

    Returns:
        准备好的消息字典列表，用于 LLM 调用。
    """
    messages = [{"role": "system", "content": system_prompt}]

    if session.messages:
        messages.extend(session.messages)

    messages.append({"role": "user", "content": task})

    return messages


def check_and_compact(
    session: ConversationSession,
    session_manager: SessionManager,
) -> bool:
    """检查会话是否需要压缩，必要时执行。

    参考 OpenCode 的做法：检查 token 数量是否超过 context window 的 95%，
    然后调用 LLM 生成摘要。

    Args:
        session: 要检查的会话对象。
        session_manager: 用于持久化的会话管理器。

    Returns:
        如果执行了压缩返回 True，否则返回 False。
    """
    compactor = Compactor(model=get_default_model())

    if compactor.should_compact(session.token_count):
        compact_and_save(session, session_manager, compactor)
        return True

    return False


def compact_and_save(
    session: ConversationSession,
    session_manager: SessionManager,
    compactor: Compactor,
) -> str:
    """压缩会话历史并持久化到数据库。

    使用 LLM 生成摘要，用摘要替换会话消息，
    更新会话 token 计数，并将摘要信息持久化到数据库。

    Args:
        session: 要压缩的会话对象。
        session_manager: 用于数据库操作的会话管理器。
        compactor: 已经判断需要压缩的压缩器实例。

    Returns:
        生成的摘要文本。
    """
    messages = session.get_messages()
    new_messages, summary = compactor.compact(messages)

    msg_id = session_manager.add_message(
        session.session_id, new_messages[0]["role"], new_messages[0]["content"]
    )

    session.messages = new_messages
    session.summary = summary
    session.summary_message_id = msg_id
    session.token_count = TokenCounter.estimate_messages(new_messages)

    session_manager.update_summary(session.session_id, summary, msg_id or 0)

    return summary


def get_memory_context(
    agent_name: str,
    memory_limit: int = DEFAULT_MEMORY_LIMIT,
) -> str:
    """从 Agent 的经验构建记忆上下文字符串。

    读取 Agent 的记忆文件并将最近的经验格式化为字符串，
    用于注入到系统提示词。

    Args:
        agent_name: Agent 名称。
        memory_limit: 包含的经验条目最大数量。

    Returns:
        格式化字符串，如 "\n你的经验：\n- 经验1\n- 经验2"，
        如果没有经验则返回空字符串。
    """
    memory = read_memory(agent_name)
    experiences = memory.get("experiences", [])

    if not experiences:
        return ""

    recent = experiences[-memory_limit:]
    lines = [f"- {e['context']}" for e in recent]
    return "\n你的经验：\n" + "\n".join(lines)
