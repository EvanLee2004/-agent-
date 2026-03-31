#!/bin/bash
# 一键清除测试数据

rm -f data/ledger.db
rm -f sessions/sessions.db
rm -f memory/*.json
echo "已清除测试数据和记忆"
