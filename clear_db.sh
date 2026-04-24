#!/bin/bash
set -euo pipefail

# 一键清除本项目运行过程中产生的本地状态。
# 这里显式解析脚本所在目录，而不是依赖调用方当前工作目录，
# 是为了避免用户在别的路径执行 `./clear_db.sh` 时误删错位置或清理不完整。
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# crewAI 初版不启用运行时记忆，会计事实只以 SQLite 账簿为准。
# 删除 `.runtime/crewai` 与 `.runtime/api` 是为了清理工作台历史和本地运行态，
# 避免“账簿清空了，但协作历史还显示上一轮结果”的假一致状态。
rm -f "$PROJECT_ROOT/data/ledger.db"
rm -rf "$PROJECT_ROOT/.runtime/crewai"
rm -rf "$PROJECT_ROOT/.runtime/api"
rmdir "$PROJECT_ROOT/.runtime" 2>/dev/null || true

# 仓库早期存在过自研 memory 目录和顶层 `__pycache__` 残留。
# 这些内容已经不属于当前产品运行路径，顺手清掉可以避免误判为仍在使用的模块。
rm -rf "$PROJECT_ROOT/memory"
find "$PROJECT_ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} +

echo "已清除账目数据库、crewAI 运行时状态和本地缓存残留"
