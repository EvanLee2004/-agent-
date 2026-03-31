#!/usr/bin/env python3
"""Accountant Execute - 执行记账操作

Usage:
    python execute.py <task> [--json]

Examples:
    python execute.py "报销1000元差旅费"
    python execute.py "收到货款5000元" --json

Author: 财务助手
Version: 1.0.0
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.ledger import write_entry
from core.rules import read_rules


def detect_anomaly(amount: float, type_: str, description: str) -> dict:
    """检测记账异常。

    Args:
        amount: 金额
        type_: 类型
        description: 描述

    Returns:
        dict: {"flag": "high"|"medium"|None, "reason": str}
    """
    anomaly = {"flag": None, "reason": None}

    if amount is None:
        return anomaly

    if amount < 10:
        anomaly["flag"] = "high"
        anomaly["reason"] = f"金额过小: {amount}元"
    elif amount > 100000:
        anomaly["flag"] = "high"
        anomaly["reason"] = f"金额过大: {amount}元"
    elif amount > 50000:
        anomaly["flag"] = "medium"
        anomaly["reason"] = f"金额较大: {amount}元，需确认"

    if "异常" in description or "问题" in description:
        if anomaly["flag"]:
            anomaly["reason"] += f"，另: {description}"
        else:
            anomaly["flag"] = "medium"
            anomaly["reason"] = description

    return anomaly


def parse_response(response: str) -> tuple:
    """从 LLM 响应中解析记账信息。

    Args:
        response: LLM 返回的文本

    Returns:
        (amount, type_, description) 元组
    """
    amount = None
    type_ = None
    description = None

    amount_match = re.search(r"金额[:：]?\s*(\d+(?:\.\d+)?)", response)
    if amount_match:
        amount = float(amount_match.group(1))

    if "支出" in response:
        type_ = "支出"
    elif "收入" in response:
        type_ = "收入"
    elif "转账" in response:
        type_ = "转账"

    desc_match = re.search(r"说明[:：]?\s*(.+?)(?:\n|$)", response)
    if desc_match:
        description = desc_match.group(1).strip()

    return amount, type_, description


def execute_accounting(task: str) -> dict:
    """执行记账操作。

    Args:
        task: 记账任务描述

    Returns:
        执行结果字典
    """
    rules = read_rules()

    prompt = (
        f"从以下任务中提取记账信息，直接回答：\n"
        f"任务：{task}\n\n"
        f"提取：金额（数字）、类型（收入/支出/转账）、说明\n"
        f"规则：\n{rules}\n\n"
        f"回答格式：金额:xxx, 类型:xxx, 说明:xxx"
    )

    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return {"status": "error", "message": "MINIMAX_API_KEY not set"}

    try:
        from core.llm import LLMClient

        messages = [
            {
                "role": "system",
                "content": f"你是财务会计，负责根据记账守则执行记账操作。\n规则：\n{rules}",
            },
            {"role": "user", "content": prompt},
        ]

        response = LLMClient.get_instance().chat(messages)
    except Exception as e:
        return {"status": "error", "message": f"LLM call failed: {str(e)}"}

    amount, type_, description = parse_response(response)

    if not amount or not type_:
        return {
            "status": "error",
            "message": f"无法理解记账信息：{response}",
            "raw_response": response,
        }

    anomaly = detect_anomaly(amount, type_ or "", description or "")

    try:
        entry_id = write_entry(
            datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            type_=type_,
            amount=float(amount),
            description=description or f"{type_} {amount}元",
            recorded_by="accountant",
            anomaly_flag=anomaly.get("flag"),
            anomaly_reason=anomaly.get("reason"),
        )
    except Exception as e:
        return {"status": "error", "message": f"Database write failed: {str(e)}"}

    result = f"[ID:{entry_id}] {type_} {amount}元"
    if description:
        result += f" - {description}"
    if anomaly.get("flag"):
        result += f" ⚠️ 异常: {anomaly['reason']}"

    return {
        "status": "ok",
        "message": result,
        "data": {
            "entry_id": entry_id,
            "amount": amount,
            "type": type_,
            "description": description,
            "anomaly": anomaly,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="执行记账操作")
    parser.add_argument("task", help="记账任务描述")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    result = execute_accounting(args.task)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        if result.get("status") == "ok":
            print(result.get("message"))
        else:
            print(f"错误: {result.get('message')}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
