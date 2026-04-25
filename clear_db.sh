#!/bin/bash
set -euo pipefail

# 一键清除本项目运行过程中产生的本地状态。
# 这里显式解析脚本所在目录，而不是依赖调用方当前工作目录，
# 是为了避免用户在别的路径执行 `./clear_db.sh` 时误删错位置或清理不完整。
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# crewAI memory 现在只保存受控会话上下文，不是财务事实来源。
# 清理数据库时必须同时删除 `.runtime/crewai` 与 `.runtime/api`，否则账簿已清空，
# 但记忆、幂等记录或协作历史仍可能让下一轮对话误以为旧凭证还存在。
rm -f "$PROJECT_ROOT/data/ledger.db"
rm -rf "$PROJECT_ROOT/.runtime/crewai"
rm -rf "$PROJECT_ROOT/.runtime/api"
rmdir "$PROJECT_ROOT/.runtime" 2>/dev/null || true

# 仓库早期存在过自研 memory 目录和顶层 `__pycache__` 残留。
# 这些内容已经不属于当前产品运行路径，顺手清掉可以避免误判为仍在使用的模块。
rm -rf "$PROJECT_ROOT/memory"
find "$PROJECT_ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} +

echo "已清除账目数据库、crewAI 运行时状态和本地缓存残留"
