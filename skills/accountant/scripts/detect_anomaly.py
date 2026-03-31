#!/usr/bin/env python3
"""Accountant Detect Anomaly - 检测记账异常

Usage:
    python detect_anomaly.py <amount> <type> [--description DESC]

Examples:
    python detect_anomaly.py 1000 支出
    python detect_anomaly.py 5 支出 --description 测试
    python detect_anomaly.py 200000 支出 --description 大额 --json

Author: 财务助手
Version: 1.0.0
"""

import argparse
import json


def detect_anomaly(amount: float, type_: str, description: str = "") -> dict:
    """检测记账异常。

    Args:
        amount: 金额
        type_: 类型（收入/支出/转账）
        description: 描述

    Returns:
        dict: {"flag": "high"|"medium"|None, "reason": str}
    """
    anomaly = {"flag": None, "reason": None}

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
        if anomaly["flag"]:
            anomaly["reason"] += f"，另: {description}"
        else:
            anomaly["flag"] = "medium"
            anomaly["reason"] = description

    return anomaly


def main():
    parser = argparse.ArgumentParser(description="检测记账异常")
    parser.add_argument("amount", type=float, help="金额")
    parser.add_argument("type", help="类型（收入/支出/转账）")
    parser.add_argument("--description", "-d", default="", help="描述")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    result = detect_anomaly(args.amount, args.type, args.description)

    if args.json:
        output = {
            "status": "ok",
            "amount": args.amount,
            "type": args.type,
            "description": args.description,
            "anomaly": result,
        }
        print(json.dumps(output, ensure_ascii=False))
    else:
        if result["flag"]:
            print(f"⚠️ 异常级别: {result['flag']}")
            print(f"原因: {result['reason']}")
        else:
            print("✅ 无异常")


if __name__ == "__main__":
    main()
