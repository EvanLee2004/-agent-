#!/usr/bin/env python3
"""Audit Skill - 审计执行脚本

Usage:
    python execute.py <record> [--json]

Examples:
    python execute.py "[ID:1] 支出 1000元 - 差旅费"
    python execute.py "[ID:2] 支出 999999元 - 备用金" --json
"""

import argparse
import json


SYSTEM_PROMPT = """你是财务审计，负责审查记账结果是否符合规则。

检查：金额是否合理、必填字段是否完整、描述是否清晰。
发现问题要标注，让对方主动修改。

审核结果：
- 通过：审核通过
- 不通过：详细说明问题
"""


def build_prompt(record: str) -> dict:
    return {
        "system": SYSTEM_PROMPT,
        "prompt": record,
        "record": record,
    }


def main():
    parser = argparse.ArgumentParser(description="审计执行")
    parser.add_argument("record")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = build_prompt(args.record)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["prompt"])


if __name__ == "__main__":
    main()
