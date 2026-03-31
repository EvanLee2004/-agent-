#!/usr/bin/env python3
"""Manager Intent - 意图分类

Usage:
    python intent.py <task> [--json]

Examples:
    python intent.py "报销1000元差旅费"
    python intent.py "查看今天的记账" --json

Author: 财务助手
Version: 1.0.0
"""

import argparse
import json
import os
import re
import sys

from openai import OpenAI


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


def classify_intent(task: str) -> dict:
    """用 LLM 分析用户意图。

    Args:
        task: 用户任务描述

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
        f"分析用户输入，判断意图：\n{task}\n\n"
        f"选项：\n"
        f"1. accounting - 记账相关（报销、收入、支出等）\n"
        f"2. review - 查看账目记录\n"
        f"3. transfer - 转账\n"
        f"4. unknown - 无法判断\n\n"
        f"直接回答选项编号或名称："
    )

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": "你是财务部门的经理，负责理解用户意图。",
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

    intent = parse_intent(llm_response)

    return {
        "status": "ok",
        "message": intent,
        "data": {"intent": intent, "raw_response": llm_response},
    }


def main():
    parser = argparse.ArgumentParser(description="意图分类")
    parser.add_argument("task", help="用户任务描述")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    result = classify_intent(args.task)

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
