#!/bin/bash
# 一键清除测试数据和记忆

rm -f data/ledger.db
rm -f memory/*.json
find memory -mindepth 1 -type f -name "*.md" -delete 2>/dev/null
rm -f .opencode/cache/*.sqlite
cat <<'EOF' > MEMORY.md
# Long-Term Memory

长期稳定的用户偏好、事实和决策。

首次运行后，系统会把真正需要长期保留的信息追加到这里。
EOF
echo "已清除账目数据库和记忆"
