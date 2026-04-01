#!/bin/bash
# 一键清除测试数据和记忆

rm -f data/ledger.db
rm -f memory/*.json
echo "已清除账目数据库和记忆"
