#!/usr/bin/env python3
"""Accounting Skill - 记账模板脚本（无具体作用）

Usage:
    python execute.py <task> [--json]

Description:
    这是一个空模板脚本，用于演示 Skill 结构。
    实际记账逻辑由 AccountantAgent 实现。
"""

import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="Accounting Skill (模板)")
    parser.add_argument("task")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = {
        "status": "ok",
        "data": {
            "skill": "accounting",
            "version": "1.0.0",
            "task": args.task,
            "message": "Accounting Skill，记账由 AccountantAgent 实现",
        },
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["data"]["message"])


if __name__ == "__main__":
    main()
