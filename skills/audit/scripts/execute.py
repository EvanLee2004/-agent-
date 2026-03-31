#!/usr/bin/env python3
"""Auditor Execute - 执行审核操作

Usage:
    python execute.py <record> [--json]

Examples:
    python execute.py "[ID:1] 支出 1000元 - 差旅费"
    python execute.py "[ID:2] 支出 999999元 - 备用金" --json

Author: 财务助手
Version: 1.0.0
"""

import argparse
import json
import os
import re
import sys
from typing import Any

from openai import OpenAI


AUDIT_RULES = """# 记账守则

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


def parse_response(response: str) -> dict:
    """从 LLM 响应中解析审核结果。

    Args:
        response: LLM 返回的文本

    Returns:
        dict: {"passed": bool, "comments": str, "anomaly_flag": str, "anomaly_reason": str}
    """
    passed = False
    comments = response
    anomaly_flag = None
    anomaly_reason = None

    if "通过" in response and "不" not in response:
        passed = True
        comments = "审核通过"
    else:
        passed = False

        flag_match = re.search(r"(high|medium|low)", response.lower())
        if flag_match:
            anomaly_flag = flag_match.group(1)

        if "金额过" in response or "金额大" in response:
            anomaly_reason = "金额异常"

    return {
        "passed": passed,
        "comments": comments,
        "anomaly_flag": anomaly_flag,
        "anomaly_reason": anomaly_reason,
    }


def execute_audit(record: str) -> dict:
    """执行审核操作。

    Args:
        record: 记账记录

    Returns:
        执行结果字典
    """
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.minimax.chat/v1")
    model = os.environ.get("LLM_MODEL", "MiniMax-M2.7")
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.3"))

    if not api_key:
        return {"status": "error", "message": "LLM_API_KEY not set"}

    prompt = (
        f"审查以下记账结果是否符合规则：\n{record}\n\n"
        f"规则：\n{AUDIT_RULES}\n\n"
        "审查要求：\n"
        "1. 逐条检查是否符合规则\n"
        "2. 如发现问题，详细说明\n"
        '3. 如无问题，说"审核通过"\n'
        "4. 不要直接说'打回'，而是标注问题让对方主动修改\n\n"
        "回答："
    )

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是财务审核，负责审查会计的记账结果是否符合规则。\n"
                    "发现问题时要标注，让会计主动修改，不要直接打回。"
                ),
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

    result = parse_response(llm_response)

    return {
        "status": "ok",
        "passed": result["passed"],
        "message": result["comments"],
        "anomaly_flag": result["anomaly_flag"],
        "anomaly_reason": result["anomaly_reason"],
    }


def main():
    parser = argparse.ArgumentParser(description="执行审核操作")
    parser.add_argument("record", help="待审核的记账记录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    result = execute_audit(args.record)

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
