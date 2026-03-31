#!/usr/bin/env python3
"""Coordination Intent Skill - 用户意图分类

本 Skill 负责分析用户输入，判断用户意图类型（记账、查询、转账等）。

Usage:
    python intent.py <task> [--json]

Examples:
    python intent.py "报销1000元差旅费"
    python intent.py "查看今天的记账" --json

Returns:
    dict: {
        "system": str,  # 系统提示词
        "prompt": str,  # 用户提示词
    }

Author: 财务助手
Version: 2.0.0
"""

import argparse
import json
import re
import sys


# =============================================================================
# 常量定义
# =============================================================================

SYSTEM_PROMPT: str = """你是财务部门的经理，负责理解用户意图。

你的职责是分析用户输入的财务相关请求，判断其意图类型。
意图类型包括：
- accounting：记账相关（报销、收入、支出等）
- review：查看账目记录
- transfer：转账
- unknown：无法判断

请直接回答意图类型，不要过多解释。
"""

PROMPT_TEMPLATE: str = """分析用户输入，判断意图：
{task}

选项：
1. accounting - 记账相关（报销、收入、支出等）
2. review - 查看账目记录
3. transfer - 转账
4. unknown - 无法判断

直接回答选项编号或名称：
"""


# =============================================================================
# 核心函数
# =============================================================================


def parse_intent(response: str) -> str:
    """从 LLM 响应文本中解析意图类型。

    Args:
        response: LLM 返回的原始文本

    Returns:
        str: 意图类型，可能的值包括：
            - "accounting": 记账相关
            - "review": 查看记录
            - "transfer": 转账
            - "unknown": 无法判断
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


def build_prompt(task: str) -> dict[str, str]:
    """构建意图分类的 prompt 数据。

    根据用户任务构建完整的对话消息，包括系统提示词和用户提示词。
    此函数不调用 LLM，只返回构建好的消息结构。

    Args:
        task: 用户输入的任务描述，如"报销1000元差旅费"

    Returns:
        dict[str, str]: 包含以下键的字典：
            - system: 系统提示词，定义角色和任务
            - prompt: 用户提示词，包含待分析的任务
    """
    return {
        "system": SYSTEM_PROMPT,
        "prompt": PROMPT_TEMPLATE.format(task=task),
    }


# =============================================================================
# CLI 入口
# =============================================================================


def main() -> None:
    """CLI 主函数。

    解析命令行参数，调用 build_prompt 构建提示词数据，
    并以 JSON 格式输出（当指定 --json 参数时）或打印提示词。
    """
    parser = argparse.ArgumentParser(
        description="意图分类 - 分析用户输入判断意图类型",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  意图分类 (默认输出):
    python intent.py "报销1000元差旅费"

  JSON 格式输出:
    python intent.py "查看今天记账" --json
        """,
    )
    parser.add_argument(
        "task",
        type=str,
        help="用户任务描述",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )
    args = parser.parse_args()

    result = build_prompt(args.task)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["prompt"])


if __name__ == "__main__":
    main()
