# Agent 架构文档

## 概述

智能会计是一个单 Agent 系统，基于 LLM 驱动的智能助手。

## 架构

```
用户 → 智能会计 → LLM 判断意图 → 执行/回复
```

## 核心模块

### accountant_agent.py

智能会计主模块，负责：
- LLM 判断用户意图（记账/查询/闲聊）
- 解析 LLM 回复中的指令
- 执行记账或查询
- 记录经验到长期记忆

### memory.py

参考 opencode 的记忆设计：
- `read_memory()` - 读取记忆
- `write_memory()` - 写入记忆
- `add_experience()` - 添加经验
- `get_memory_context()` - 获取格式化上下文

### ledger.py

账目数据库：
- `write_entry()` - 写入账目
- `get_entries()` - 查询账目
- `update_entry_status()` - 更新状态

### llm.py

LLM 调用封装：
- 单例模式
- 支持自定义 base_url 和 model

## 记忆系统

记忆存储在 `memory/智能会计.json`：

```json
{
  "agent": "智能会计",
  "experiences": [
    {
      "type": "记账",
      "content": "报销差旅费300元",
      "result": "记账成功 [ID:2]",
      "learned_at": "2026-04-01"
    }
  ]
}
```

每次交互后自动记录经验，经验上下文注入系统提示词。
