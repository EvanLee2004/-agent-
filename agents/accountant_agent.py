"""智能会计 - 单 Agent 处理所有财务任务"""

import re
from datetime import datetime
from typing import Optional

from infrastructure.llm import LLMClient
from infrastructure.ledger import write_entry, get_entries
from infrastructure.memory import (
    get_memory_context,
    add_experience,
    format_experience,
)


BASE_SYSTEM_PROMPT = """你是专业的智能会计助手。

你需要理解用户意图并执行相应操作：

【记账】
当用户提供金额、日期、类型（收入/支出）时，回复格式：
【记账】日期:2024-01-15|金额:500|类型:支出|说明:客户拜访交通费

【查询】
当用户想查看账目时，回复格式：
【查询】日期:2024-01-15（可选，模糊查询）

【闲聊】
问候、感谢、身份询问等非任务输入，直接友好回复。

记账规则：
- 金额超过50000标注"需审核"
- 金额低于10元标注"金额过小"
- 必须包含日期、类型、金额、说明

回复示例：
- "报销500元" → 【记账】日期:{今天}|金额:500|类型:支出|说明:报销
- "查看账目" → 【查询】
- "你好" → 你好！我是智能会计，有任何财务问题请告诉我～

【重要】每次成功处理任务后，我会记录经验以便学习。"""


def get_system_prompt() -> str:
    """获取带有记忆上下文的系统提示词"""
    memory_context = get_memory_context("智能会计")
    return BASE_SYSTEM_PROMPT + memory_context if memory_context else BASE_SYSTEM_PROMPT


def parse_accounting(text: str) -> Optional[dict]:
    """从 LLM 回复中解析记账信息"""
    match = re.search(
        r"【记账】日期:([^|]+)\|金额:([^|]+)\|类型:([^|]+)\|说明:(.+)",
        text
    )
    if not match:
        return None

    date = match.group(1).strip()
    amount = float(match.group(2).strip())
    type_ = match.group(3).strip()
    desc = match.group(4).strip()

    # 异常标注
    anomaly_flag = None
    anomaly_reason = None
    if amount > 50000:
        anomaly_flag = "high"
        anomaly_reason = "金额超过50000，需审核"
    elif amount < 10:
        anomaly_flag = "low"
        anomaly_reason = "金额过小"

    return {
        "date": date,
        "amount": amount,
        "type": type_,
        "description": desc,
        "anomaly_flag": anomaly_flag,
        "anomaly_reason": anomaly_reason,
    }


def execute_accounting(info: dict) -> int:
    """执行记账"""
    return write_entry(
        datetime=info["date"] + " " + datetime.now().strftime("%H:%M:%S"),
        type_=info["type"],
        amount=info["amount"],
        description=info["description"],
        recorded_by="智能会计",
        anomaly_flag=info.get("anomaly_flag"),
        anomaly_reason=info.get("anomaly_reason"),
    )


def format_entries(entries: list[dict]) -> str:
    """格式化账目列表"""
    if not entries:
        return "暂无账目记录"

    lines = []
    for e in entries:
        status = "✓" if e["status"] == "approved" else "⏳"
        lines.append(
            f"[{e['id']}] {status} {e['datetime']} | {e['type']} {e['amount']}元 | {e['description']}"
        )
    return "\n".join(lines)


def learn_from_interaction(user_input: str, result: str, intent: str) -> None:
    """从交互中学习，记录经验

    Args:
        user_input: 用户输入
        result: 处理结果
        intent: 识别的意图（记账/查询/闲聊）
    """
    if intent == "accounting" and "记账成功" in result:
        exp = format_experience(
            action="记账",
            content=user_input[:100],
            result=result,
        )
        add_experience("智能会计", exp)
    elif intent == "query" and "暂无" not in result and "解析" not in result:
        exp = format_experience(
            action="查询",
            content=user_input,
            result="查询成功" if "ID:" in result else result[:50],
        )
        add_experience("智能会计", exp)


async def handle(user_input: str) -> str:
    """处理用户输入"""
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": user_input},
    ]

    resp = LLMClient.get_instance().chat(messages)
    content = resp.content.strip()

    # 检查是否需要记账
    if "【记账】" in content:
        info = parse_accounting(content)
        if info:
            entry_id = execute_accounting(info)
            result = f"记账成功 [ID:{entry_id}]"
            if info.get("anomaly_reason"):
                result += f"（{info['anomaly_reason']}）"
            learn_from_interaction(user_input, result, "accounting")
            return result
        learn_from_interaction(user_input, "解析失败", "accounting")
        return "记账信息解析失败，请重试"

    # 检查是否需要查询
    if "【查询】" in content:
        date_match = re.search(r"【查询】日期:(\S+)", content)
        date = date_match.group(1) if date_match else None
        entries = get_entries(date=date) if date else get_entries()
        result = format_entries(entries)
        learn_from_interaction(user_input, result, "query")
        return result

    # 其他情况直接返回 LLM 回复
    return content
