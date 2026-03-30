"""记忆读写模块，供各 Agent 公用"""

import json
from pathlib import Path


def read_memory(agent_name: str) -> dict:
    """读取指定 Agent 的记忆文件"""
    path = Path("memory") / f"{agent_name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"agent": agent_name, "experiences": []}


def write_memory(agent_name: str, memory: dict) -> None:
    """写入指定 Agent 的记忆文件"""
    Path("memory").mkdir(exist_ok=True)
    path = Path("memory") / f"{agent_name}.json"
    path.write_text(json.dumps(memory, ensure_ascii=False, indent=2))
