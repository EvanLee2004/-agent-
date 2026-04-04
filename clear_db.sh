#!/bin/bash
# 一键清除测试数据和 DeerFlow 运行时状态
# 记忆数据现在由 DeerFlow 原生管理，存放在 .runtime/deerflow/home/agents/*/memory.json

rm -f data/ledger.db
rm -rf .runtime/deerflow
echo "已清除账目数据库和 DeerFlow 运行时状态（含记忆）"
