"""记忆读写模块，供各 Agent 公用。

提供 Agent 长期记忆的持久化存储。
"""

import json
from pathlib import Path


def read_memory(agent_name: str) -> dict:
    """读取指定 Agent 的记忆文件。

    Args:
        agent_name: Agent 名称，对应 memory/{agent_name}.json

    Returns:
        记忆字典，包含 'agent' 和 'experiences' 键。
        如果文件不存在，返回空模板。
    """
    path = Path("memory") / f"{agent_name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"agent": agent_name, "experiences": []}


def write_memory(agent_name: str, memory: dict) -> None:
    """写入指定 Agent 的记忆文件。

    Args:
        agent_name: Agent 名称。
        memory: 要写入的记忆字典。
    """
    Path("memory").mkdir(exist_ok=True)
    path = Path("memory") / f"{agent_name}.json"
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2))
