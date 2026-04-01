#!/usr/bin/env python3
"""Accounting Execute Skill - 执行记账操作

本 Skill 负责从用户输入中提取记账信息，构建提示词数据。
不直接调用 LLM，由 Agent 层统一调用。

Usage:
    python execute.py <task> [--json] [--feedback]

Examples:
    python execute.py "报销1000元差旅费"
    python execute.py "收到货款5000元" --json
    python execute.py "报销500元" --feedback "金额过小"

Returns:
    dict: {
        "system": str,  # 系统提示词
        "prompt": str,  # 用户提示词
        "task": str,    # 原始任务
        "feedback": str, # 审核反馈
    }

Author: 财务助手
Version: 2.0.0
"""

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Optional


# =============================================================================
# 常量定义 - 记账规则（内联，不依赖外部文件）
# =============================================================================

ACCOUNTING_RULES: str = """# 记账守则

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

SYSTEM_PROMPT: str = f"""你是财务会计，负责根据记账守则执行记账操作。
规则：
{ACCOUNTING_RULES}"""

PROMPT_TEMPLATE: str = """从以下任务中提取记账信息，直接回答：
任务：{task}

提取：日期（格式YYYY-MM-DD）、金额（数字）、类型（收入/支出/转账）、说明{correction}
规则：
{ACCOUNTING_RULES}

回答格式：日期:YYYY-MM-DD, 金额:xxx, 类型:xxx, 说明:xxx"""


# =============================================================================
# 核心函数
# =============================================================================


def detect_anomaly(
    amount: float, type_: str, description: str = ""
) -> dict[str, Optional[str]]:
    """检测记账金额异常。

    根据金额大小和描述内容检测潜在的异常情况。

    Args:
        amount: 金额（数字）
        type_: 收支类型（收入/支出/转账）
        description: 记账描述

    Returns:
        dict[str, Optional[str]]: 异常检测结果，包含：
            - flag: 异常级别 ("high"/"medium"/None)
            - reason: 异常原因描述
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
    """从 LLM 响应文本中解析记账信息。

    使用正则表达式从 LLM 返回的文本中提取金额、类型、说明。

    Args:
        response: LLM 返回的原始文本

    Returns:
        tuple: 包含三个元素的元组
            - amount (float | None): 金额
            - type_ (str | None): 类型（收入/支出/转账）
            - description (str | None): 说明
    """
    amount: Optional[float] = None
    type_: Optional[str] = None
    description: Optional[str] = None

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


def build_prompt(task: str, feedback: str = "") -> dict[str, str]:
    """构建记账的 prompt 数据。

    根据用户任务和审核反馈构建完整的对话消息。
    此函数不调用 LLM，只返回构建好的消息结构。

    Args:
        task: 记账任务描述，如"报销1000元差旅费"
        feedback: 可选的审核反馈，用于修正之前的错误

    Returns:
        dict[str, str]: 包含以下键的字典：
            - system: 系统提示词，包含角色定义和规则
            - prompt: 用户提示词，包含待提取的任务
            - task: 原始任务描述
            - feedback: 审核反馈（如果提供）
    """
    correction: str = ""
    if feedback:
        correction = f"\n\n重要：请根据以下审核反馈修正记账信息：\n{feedback}"

    prompt: str = PROMPT_TEMPLATE.format(
        task=task, correction=correction, ACCOUNTING_RULES=ACCOUNTING_RULES
    )

    return {
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "task": task,
        "feedback": feedback,
    }


def parse_and_build_result(task: str, llm_response: str, feedback: str = "") -> dict:
    """解析 LLM 响应并构建记账结果。

    从 LLM 返回的文本中提取记账信息，检测异常，构建完整的结果字典。

    Args:
        task: 原始任务描述
        llm_response: LLM 返回的文本
        feedback: 审核反馈（如果有）

    Returns:
        dict: 包含记账结果的字典，包括：
            - status: 执行状态 ("ok"/"error")
            - message: 待确认的消息
            - data: 详细的记账数据
                - amount: 金额
                - type: 类型
                - description: 说明
                - anomaly: 异常信息
                - datetime: 时间戳
                - recorded_by: 记录人
    """
    amount, type_, description = parse_response(llm_response)

    if not amount or not type_:
        return {
            "status": "error",
            "message": f"无法理解记账信息：{llm_response}",
            "raw_response": llm_response,
        }

    anomaly: dict[str, Optional[str]] = detect_anomaly(
        amount, type_ or "", description or ""
    )

    return {
        "status": "ok",
        "message": f"[待确认] {type_} {amount}元 - {description or '无说明'}",
        "data": {
            "amount": amount,
            "type": type_,
            "description": description or f"{type_} {amount}元",
            "anomaly": anomaly,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "recorded_by": "accounting",
            "task": task,
            "feedback": feedback,
        },
    }


# =============================================================================
# CLI 入口
# =============================================================================


def main() -> None:
    """CLI 主函数。

    解析命令行参数，调用 build_prompt 构建提示词数据，
    并以 JSON 格式输出。
    """
    parser = argparse.ArgumentParser(
        description="执行记账操作 - 从任务中提取记账信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  基本记账:
    python execute.py "报销1000元差旅费"

  JSON 格式输出:
    python execute.py "收到货款5000元" --json

  带审核反馈修正:
    python execute.py "报销500元" --feedback "金额过小，请确认"
        """,
    )
    parser.add_argument(
        "task",
        type=str,
        help="记账任务描述",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )
    parser.add_argument(
        "--feedback",
        "-f",
        type=str,
        default="",
        help="审核反馈，用于修正错误",
    )
    args = parser.parse_args()

    result: dict = build_prompt(args.task, args.feedback)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["prompt"])


if __name__ == "__main__":
    main()
