"""智能会计 - 单 Agent 处理所有财务任务"""

import json
import re
from datetime import datetime
from typing import Optional, Any

from infrastructure.llm import LLMClient, LLMResponse
from infrastructure.ledger import write_entry, get_entries
from infrastructure.memory import (
    get_memory_context,
    add_experience,
    format_experience,
)
from infrastructure.skill_loader import SkillLoader


BASE_SYSTEM_PROMPT = """你是专业的智能会计助手。

你需要理解用户意图并以结构化 JSON 格式回复。

【输出格式】
回复必须使用以下 JSON 格式，禁止使用【记账】【查询】等标记：
{"intent": "accounting", "data": {"date": "YYYY-MM-DD", "amount": 500, "type": "收入|支出", "description": "..."}}
{"intent": "query", "data": {"date": "YYYY-MM-DD"}}
{"intent": "chat", "data": {"reply": "直接回复内容"}}

【intent=accounting 时 data 字段】
- date: 日期，YYYY-MM-DD 格式
- amount: 金额数字（正数）
- type: 收入 或 支出
- description: 描述说明

【intent=query 时 data 字段】
- date: 可选，YYYY-MM-DD 格式，支持模糊查询

【intent=chat 时 data 字段】
- reply: 直接回复内容

【记账规则】
- 金额超过50000标注"需审核"
- 金额低于10元标注"金额过小"

【示例】
- 用户: "报销500元" → {"intent": "accounting", "data": {"date": "今天日期", "amount": 500, "type": "支出", "description": "报销"}}
- 用户: "查看账目" → {"intent": "query", "data": {}}
- 用户: "你好" → {"intent": "chat", "data": {"reply": "你好！我是智能会计..."}}

【重要】每次成功处理任务后，我会记录经验以便学习。"""


def get_system_prompt() -> str:
    """获取带有记忆上下文的系统提示词"""
    memory_context = get_memory_context("智能会计")
    return BASE_SYSTEM_PROMPT + memory_context if memory_context else BASE_SYSTEM_PROMPT


def parse_intent(text: str) -> Optional[dict]:
    """解析 LLM 回复中的意图和数据

    优先使用 JSON 解析，失败时降级到正则匹配。

    Args:
        text: LLM 返回的原始文本

    Returns:
        解析后的 dict: {"intent": "...", "data": {...}}
        解析失败返回 None
    """
    text = text.strip()

    json_result = _parse_json_intent(text)
    if json_result:
        return json_result

    regex_result = _parse_regex_intent(text)
    if regex_result:
        return regex_result

    return None


def _parse_json_intent(text: str) -> Optional[dict]:
    """尝试 JSON 格式解析"""
    try:
        data = json.loads(text)

        if not isinstance(data, dict):
            return None

        intent = data.get("intent")
        if intent not in ("accounting", "query", "chat"):
            return None

        intent_data = data.get("data", {})

        if intent == "accounting":
            required = ["date", "amount", "type", "description"]
            if not all(k in intent_data for k in required):
                return None
            intent_data["amount"] = float(intent_data["amount"])

            amount = intent_data["amount"]
            if amount > 50000:
                intent_data["anomaly_flag"] = "high"
                intent_data["anomaly_reason"] = "金额超过50000，需审核"
            elif amount < 10:
                intent_data["anomaly_flag"] = "low"
                intent_data["anomaly_reason"] = "金额过小"

        return {"intent": intent, "data": intent_data}

    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _parse_regex_intent(text: str) -> Optional[dict]:
    """降级：使用正则表达式解析（兼容旧格式）"""
    match = re.search(
        r"【记账】日期:([^|]+)\|金额:([^|]+)\|类型:([^|]+)\|说明:(.+)",
        text,
    )
    if match:
        date = match.group(1).strip()
        amount = float(match.group(2).strip())
        type_ = match.group(3).strip()
        desc = match.group(4).strip()

        anomaly_flag = None
        anomaly_reason = None
        if amount > 50000:
            anomaly_flag = "high"
            anomaly_reason = "金额超过50000，需审核"
        elif amount < 10:
            anomaly_flag = "low"
            anomaly_reason = "金额过小"

        return {
            "intent": "accounting",
            "data": {
                "date": date,
                "amount": amount,
                "type": type_,
                "description": desc,
                "anomaly_flag": anomaly_flag,
                "anomaly_reason": anomaly_reason,
            },
        }

    query_match = re.search(r"【查询】(?:日期:(\S+))?", text)
    if query_match:
        return {
            "intent": "query",
            "data": {"date": query_match.group(1)} if query_match.group(1) else {},
        }

    return None


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
        intent: 识别的意图（accounting/query/chat）
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


class AccountantAgent:
    """智能会计 Agent - 支持依赖注入和 Skill 系统"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """初始化 Agent

        Args:
            llm_client: LLM 客户端实例，为 None 时使用单例
        """
        self._llm_client = llm_client
        self._skill_loader = SkillLoader()

    @property
    def llm_client(self) -> LLMClient:
        """获取 LLM 客户端（懒加载单例）"""
        if self._llm_client is None:
            self._llm_client = LLMClient.get_instance()
        return self._llm_client

    def _execute_skill_accounting(self, user_input: str) -> Optional[dict]:
        """尝试使用 Skill 执行记账

        Args:
            user_input: 用户输入

        Returns:
            Skill 执行成功返回记账数据 dict，失败返回 None
        """
        try:
            result = self._skill_loader.execute_script(
                "accounting",
                "execute",
                [user_input, "--json"],
                timeout=10,
            )

            if result.get("status") == "ok":
                data = result.get("data", {})
                if isinstance(data, dict) and "task" in data:
                    task_text = data["task"]
                    parsed = parse_intent(
                        json.dumps(
                            {
                                "intent": "accounting",
                                "data": {
                                    "date": datetime.now().strftime("%Y-%m-%d"),
                                    "amount": 0,
                                    "type": "支出",
                                    "description": task_text,
                                },
                            }
                        )
                    )
                    if parsed:
                        return parsed["data"]
            return None

        except Exception:
            return None

    def _execute_skill_audit(self, entry_info: dict) -> Optional[dict]:
        """尝试使用 Skill 执行审核

        Args:
            entry_info: 账目信息 dict

        Returns:
            Skill 执行成功返回审核结果 dict，失败返回 None
        """
        try:
            record = f"[ID:{entry_info.get('id', '?')}] {entry_info.get('type', '')} {entry_info.get('amount', 0)}元 - {entry_info.get('description', '')}"
            result = self._skill_loader.execute_script(
                "audit",
                "execute",
                [record, "--json"],
                timeout=10,
            )

            if result.get("status") == "ok":
                return result.get("data")
            return None

        except Exception:
            return None

    async def handle(self, user_input: str) -> str:
        """处理用户输入"""
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_input},
        ]

        resp: LLMResponse = self.llm_client.chat(messages)

        if not resp.success:
            return f"服务暂时不可用，请稍后重试。({resp.error_message})"

        content = resp.content.strip()
        parsed = parse_intent(content)

        if not parsed:
            return content

        intent = parsed["intent"]
        data = parsed["data"]

        if intent == "accounting":
            skill_data = self._execute_skill_accounting(user_input)
            if skill_data:
                data = skill_data

            try:
                entry_id = execute_accounting(data)
                result = f"记账成功 [ID:{entry_id}]"
                if data.get("anomaly_reason"):
                    result += f"（{data['anomaly_reason']}）"
                learn_from_interaction(user_input, result, "accounting")
                return result
            except (KeyError, ValueError) as e:
                learn_from_interaction(user_input, "解析失败", "accounting")
                return f"记账信息解析失败，请重试。({str(e)})"

        elif intent == "query":
            date = data.get("date")
            entries = get_entries(date=date) if date else get_entries()
            result = format_entries(entries)
            learn_from_interaction(user_input, result, "query")
            return result

        elif intent == "chat":
            return data.get("reply", content)

        return content


async def handle(user_input: str) -> str:
    """处理用户输入（向后兼容的模块级函数）

    使用单例 LLMClient，优先使用 AccountantAgent 类进行依赖注入。
    """
    agent = AccountantAgent()
    return await agent.handle(user_input)
