#!/usr/bin/env python3
"""Audit Execute Skill - 执行审核操作

本 Skill 负责审核记账结果，检查是否符合规则。
不直接调用 LLM，由 Agent 层统一调用。

Usage:
    python execute.py <record> [--json]

Examples:
    python execute.py "[ID:1] 支出 1000元 - 差旅费"
    python execute.py "[ID:2] 支出 999999元 - 备用金" --json

Returns:
    dict: {
        "system": str,  # 系统提示词
        "prompt": str,  # 用户提示词
        "record": str,  # 原始记录
    }

Author: 财务助手
Version: 2.0.0
"""

import argparse
import json
import re
import sys
from typing import Any


# =============================================================================
# 常量定义 - 审核规则（内联，不依赖外部文件）
# =============================================================================

AUDIT_RULES: str = """# 记账守则

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

SYSTEM_PROMPT: str = """你是财务审核，负责审查会计的记账结果是否符合规则。
发现问题时要标注，让会计主动修改，不要直接打回。"""

PROMPT_TEMPLATE: str = """审查以下记账结果是否符合规则：
{record}

规则：
{AUDIT_RULES}

审查要求：
1. 逐条检查是否符合规则
2. 如发现问题，详细说明
3. 如无问题，说"审核通过"
4. 不要直接说'打回'，而是标注问题让对方主动修改

回答："""


# =============================================================================
# 核心函数
# =============================================================================


def parse_response(response: str) -> dict[str, Any]:
    """从 LLM 响应文本中解析审核结果。

    判断审核是否通过，提取异常标记和原因。

    Args:
        response: LLM 返回的原始文本

    Returns:
        dict[str, Any]: 包含以下键的字典：
            - passed: bool, 是否通过
            - comments: str, 审核意见
            - anomaly_flag: str | None, 异常级别 (high/medium/low)
            - anomaly_reason: str | None, 异常原因
    """
    passed: bool = False
    comments: str = response
    anomaly_flag: Any = None
    anomaly_reason: Any = None

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


def build_prompt(record: str) -> dict[str, str]:
    """构建审核的 prompt 数据。

    根据待审核的记账记录构建完整的对话消息。
    此函数不调用 LLM，只返回构建好的消息结构。

    Args:
        record: 待审核的记账记录，如 "[ID:1] 支出 1000元 - 差旅费"

    Returns:
        dict[str, str]: 包含以下键的字典：
            - system: 系统提示词，包含角色定义和审核要求
            - prompt: 用户提示词，包含待审核的记录
            - record: 原始记账记录
    """
    prompt: str = PROMPT_TEMPLATE.format(
        record=record,
        AUDIT_RULES=AUDIT_RULES,
    )

    return {
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "record": record,
    }


def parse_and_build_result(record: str, llm_response: str) -> dict[str, Any]:
    """解析 LLM 响应并构建审核结果。

    Args:
        record: 原始记账记录
        llm_response: LLM 返回的文本

    Returns:
        dict[str, Any]: 包含以下键的字典：
            - status: 执行状态 ("ok")
            - passed: bool, 是否通过
            - message: str, 审核意见
            - anomaly_flag: str | None, 异常级别
            - anomaly_reason: str | None, 异常原因
            - record: str, 原始记录
    """
    result: dict[str, Any] = parse_response(llm_response)

    return {
        "status": "ok",
        "passed": result["passed"],
        "message": result["comments"],
        "anomaly_flag": result["anomaly_flag"],
        "anomaly_reason": result["anomaly_reason"],
        "record": record,
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
        description="执行审核操作 - 审查记账结果是否符合规则",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  基本审核:
    python execute.py "[ID:1] 支出 1000元 - 差旅费"

  JSON 格式输出:
    python execute.py "[ID:2] 支出 999999元 - 备用金" --json
        """,
    )
    parser.add_argument(
        "record",
        type=str,
        help="待审核的记账记录",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )
    args = parser.parse_args()

    result: dict = build_prompt(args.record)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["prompt"])


if __name__ == "__main__":
    main()
