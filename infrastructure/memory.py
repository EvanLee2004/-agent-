"""记忆模块 - 参考 opencode 的长期记忆设计。

功能：
1. 读取历史经验（experiences）
2. 格式化记忆上下文
3. 追加新经验
4. 自动清理过期记忆

opencode 记忆结构：
- agent/：智能体名称
- experiences/：历史经验列表
- context/：累积的上下文摘要
"""

import json
from pathlib import Path
from datetime import datetime


MEMORY_DIR = Path("memory")
DEFAULT_MEMORY_LIMIT = 10  # 保留最近 N 条经验


def read_memory(agent_name: str) -> dict:
    """读取指定 Agent 的记忆文件"""
    path = MEMORY_DIR / f"{agent_name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "agent": agent_name,
        "experiences": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def write_memory(agent_name: str, memory: dict) -> None:
    """写入记忆文件"""
    MEMORY_DIR.mkdir(exist_ok=True)
    memory["updated_at"] = datetime.now().isoformat()
    path = MEMORY_DIR / f"{agent_name}.json"
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2))


def add_experience(agent_name: str, experience: dict) -> None:
    """添加一条经验到记忆

    Args:
        agent_name: Agent 名称
        experience: 经验内容，如 {"type": "记账", "content": "...", "result": "成功"}
    """
    memory = read_memory(agent_name)

    # 添加时间戳
    experience["learned_at"] = datetime.now().strftime("%Y-%m-%d")

    # 添加到经验列表开头（最新的在前面）
    memory["experiences"].insert(0, experience)

    # 限制数量，避免记忆文件过大
    if len(memory["experiences"]) > DEFAULT_MEMORY_LIMIT * 2:
        memory["experiences"] = memory["experiences"][:DEFAULT_MEMORY_LIMIT]

    write_memory(agent_name, memory)


def get_memory_context(agent_name: str, limit: int = DEFAULT_MEMORY_LIMIT) -> str:
    """获取格式化后的记忆上下文，用于注入系统提示词

    Args:
        agent_name: Agent 名称
        limit: 最多包含的经验条数

    Returns:
        格式化后的记忆字符串，如果无记忆则返回空字符串
    """
    memory = read_memory(agent_name)
    experiences = memory.get("experiences", [])

    if not experiences:
        return ""

    # 取最近的经验
    recent = experiences[:limit]

    # 格式化为记忆上下文
    lines = ["\n\n【历史经验】"]
    for exp in recent:
        exp_type = exp.get("type", "经验")
        exp_content = exp.get("content", "")[:100]  # 限制长度
        exp_result = exp.get("result", "")
        learned_at = exp.get("learned_at", "")

        lines.append(f"- [{learned_at}] {exp_type}: {exp_content}")
        if exp_result:
            lines.append(f"  结果: {exp_result}")

    return "\n".join(lines)


def clear_memory(agent_name: str) -> None:
    """清空指定 Agent 的记忆"""
    memory = read_memory(agent_name)
    memory["experiences"] = []
    write_memory(agent_name, memory)


def format_experience(action: str, content: str, result: str, feedback: str = "") -> dict:
    """格式化一条经验

    Args:
        action: 操作类型，如"记账"、"审核"
        content: 操作内容摘要
        result: 操作结果
        feedback: 反馈/反思（可选）

    Returns:
        格式化的经验字典
    """
    exp = {
        "type": action,
        "content": content[:200],  # 限制长度
        "result": result[:100],
    }
    if feedback:
        exp["feedback"] = feedback[:200]
    return exp
