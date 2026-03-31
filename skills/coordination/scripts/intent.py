#!/usr/bin/env python3
"""Coordination Intent - 意图分类

Usage:
    python intent.py <task> [--json]

Examples:
    python intent.py "报销1000元差旅费"
    python intent.py "查看今天的记账" --json

Author: 财务助手
Version: 2.0.0
"""

import argparse
import json
import re
import sys


SYSTEM_PROMPT = "你是财务部门的经理，负责理解用户意图。"

PROMPT_TEMPLATE = """分析用户输入，判断意图：
{task}

选项：
1. accounting - 记账相关（报销、收入、支出等）
2. review - 查看账目记录
3. transfer - 转账
4. unknown - 无法判断

直接回答选项编号或名称："""


def parse_intent(response: str) -> str:
    """从 LLM 响应中解析意图。

    Args:
        response: LLM 返回的文本

    Returns:
        意图类型：accounting / review / transfer / unknown
    """
    response_lower = response.lower().strip()
    response_num = response_lower.split(".")[0].strip()

    if response_num == "2":
        return "review"
    elif response_num == "3":
        return "transfer"
    elif (
        response_num == "1"
        or "accounting" in response_lower
        or "记账" in response
        or "报销" in response
    ):
        return "accounting"
    else:
        return "unknown"


def build_prompt(task: str) -> dict:
    """构建意图分类的 prompt 数据。

    Args:
        task: 用户任务描述

    Returns:
        包含 system 和 prompt 的字典
    """
    return {
        "system": SYSTEM_PROMPT,
        "prompt": PROMPT_TEMPLATE.format(task=task),
    }


def main():
    parser = argparse.ArgumentParser(description="意图分类")
    parser.add_argument("task", help="用户任务描述")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    result = build_prompt(args.task)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["prompt"])


if __name__ == "__main__":
    main()
