#!/usr/bin/env python3
"""Accounting Skill - 记账执行脚本

Usage:
    python execute.py <task> [--json]

Examples:
    python execute.py "报销1000元差旅费"
    python execute.py "收到货款5000元" --json
"""

import argparse
import json


SYSTEM_PROMPT = """你是记账专家，负责执行记账操作。

从任务中提取：日期(YYYY-MM-DD)、金额(数字)、类型(收入/支出)、说明。

规则：
- 金额必须为正数
- 类型只能是：收入、支出
- 回复格式：【记账】日期:2024-01-15|金额:500|类型:支出|说明:客户拜访
"""


def build_prompt(task: str) -> dict:
    return {
        "system": SYSTEM_PROMPT,
        "prompt": task,
        "task": task,
    }


def main():
    parser = argparse.ArgumentParser(description="记账执行")
    parser.add_argument("task")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = build_prompt(args.task)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["prompt"])


if __name__ == "__main__":
    main()
