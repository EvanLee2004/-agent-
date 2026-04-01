#!/usr/bin/env python3
"""Rules Skill - 规则模板脚本（无具体作用）

Usage:
    python execute.py <input> [--json]

Description:
    这是一个空模板脚本，用于演示 Skill 结构。
    实际规则应用由 AccountantAgent 在代码中实现。
"""

import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="Rules Skill (模板)")
    parser.add_argument("input")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = {
        "status": "ok",
        "data": {
            "skill": "rules",
            "version": "2.0.0",
            "input": args.input,
            "message": "Rules Skill v2.0 中国会计准则",
        },
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["data"]["message"])


if __name__ == "__main__":
    main()
