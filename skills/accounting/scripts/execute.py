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
from typing import Any, Optional

from openai import OpenAI


ACCOUNTING_RULES = """# 记账守则

## 基本原则

1. 所有收支必须记录日期、金额、类型（收入/支出）、说明
2. 发票或凭证必须妥善保存
3. 大额支出（>5000元）需提前申请

## 收入记录

- 类型填写"收入"
- 说明写明来源（如：客户付款、销售收入）
- 金额为正数

## 支出记录

- 类型填写"支出"
- 说明写明用途（如：办公用品、差旅费）
- 金额为正数
- 需附发票

## 转账记录

- 类型填写"转账"
- 说明写明转账双方和原因
- 金额为正数

## 审批流程

1. 会计初录
2. 审核复核
3. 通过后正式入账"""


def detect_anomaly(
    amount: float, type_: str, description: str = ""
) -> dict[str, Optional[str]]:
    """检测记账异常。

    Args:
        amount: 金额
        type_: 类型
        description: 描述

    Returns:
        dict: {"flag": "high"|"medium"|None, "reason": str}
    """
    anomaly: dict[str, Optional[str]] = {"flag": None, "reason": None}

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
        if anomaly["flag"] and anomaly["reason"]:
            anomaly["reason"] = f"{anomaly['reason']}，另: {description}"
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


def execute_accounting(task: str, feedback: str = "") -> dict:
    """执行记账操作。

    Args:
        task: 记账任务描述
        feedback: 可选的审核反馈，用于修正错误

    Returns:
        执行结果字典（包含记账数据，Agent 层负责写入数据库）
    """
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.minimax.chat/v1")
    model = os.environ.get("LLM_MODEL", "MiniMax-M2.7")
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.3"))

    if not api_key:
        return {"status": "error", "message": "LLM_API_KEY not set"}

    correction = ""
    if feedback:
        correction = f"\n\n重要：请根据以下审核反馈修正记账信息：\n{feedback}"

    prompt = (
        f"从以下任务中提取记账信息，直接回答：\n"
        f"任务：{task}\n\n"
        f"提取：金额（数字）、类型（收入/支出/转账）、说明{correction}\n"
        f"规则：\n{ACCOUNTING_RULES}\n\n"
        f"回答格式：金额:xxx, 类型:xxx, 说明:xxx"
    )

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        messages = [
            {
                "role": "system",
                "content": f"你是财务会计，负责根据记账守则执行记账操作。\n规则：\n{ACCOUNTING_RULES}",
            },
            {"role": "user", "content": prompt},
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
        )
        llm_response = response.choices[0].message.content or ""
    except Exception as e:
        return {"status": "error", "message": f"LLM call failed: {str(e)}"}

    amount, type_, description = parse_response(llm_response)

    if not amount or not type_:
        return {
            "status": "error",
            "message": f"无法理解记账信息：{llm_response}",
            "raw_response": llm_response,
        }

    anomaly = detect_anomaly(amount, type_ or "", description or "")

    return {
        "status": "ok",
        "message": f"[待确认] {type_} {amount}元 - {description or '无说明'}",
        "data": {
            "amount": amount,
            "type": type_,
            "description": description or f"{type_} {amount}元",
            "anomaly": anomaly,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recorded_by": "accountant",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="执行记账操作")
    parser.add_argument("task", help="记账任务描述")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--feedback", "-f", default="", help="审核反馈，用于修正错误")
    args = parser.parse_args()

    result = execute_accounting(args.task, args.feedback)

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
