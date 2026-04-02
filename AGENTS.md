# Agent 开发指南

本文档面向在本仓库中工作的 AI Agent。

生成的代码要带详细中文注释，但注释要解释“为什么这样设计”，不要只重复代码行为。

## 项目概述

智能会计是一个单 Agent 系统，当前采用按功能模块组织的架构：

```text
用户
  ↓
ConversationRouter
  ↓
ConversationService
  ↓
PromptContextService
  ↓
ToolLoopService
  ↓
Feature Tool Routers
  ↓
Feature Services
  ↓
Repositories
```

主流程已经完全切换到原生 function calling，不再依赖旧的 JSON 意图解析链路。

## 运行命令

### 启动应用
```bash
python main.py
```

### 配置 API Key
```bash
echo "LLM_API_KEY=your_key" > .env
```

### 运行测试
```bash
./.venv/bin/python -B -m unittest discover -s tests -v
```

### 清理数据库与记忆
```bash
./clear_db.sh
```

## 当前目录结构

```text
├── main.py
├── app/
├── conversation/
├── accounting/
├── audit/
├── tax/
├── memory/
├── rules/
├── llm/
├── configuration/
├── .agent_assets/
│   └── skills/
├── MEMORY.md
├── tests/
└── config.json
```

## 开发规则

### 1. 严格分层

- `router -> service -> repository -> model`
- 禁止跨层直接调用
- 具体实现只允许在 `app/` 装配

### 2. 按功能模块组织

- 目录按业务功能拆分，不按“types / services / infrastructure”分组
- 一个文件一个类
- 禁止新增 `utils.py` / `helpers.py`

### 3. 工具调用主链路

- `conversation/` 负责会话编排
- `ToolLoopService` 负责原生 function calling 循环
- 各 feature 自己提供 tool router
- 业务规则必须留在 feature service，不得塞进 router

### 4. 账务真相

- 主账只有：
  - `account_subject`
  - `journal_voucher`
  - `journal_line`
- 不允许重新引入旧 `ledger` 兼容体系

### 5. 记忆系统

- 长期记忆：`MEMORY.md`
- 每日记忆：`memory/YYYY-MM-DD.md`
- Markdown 是源数据
- SQLite FTS 只做搜索索引
- 记忆事实类问题必须先查询 `search_memory`

## Skills

当前业务核心 skills：

- `accounting`
- `tax`
- `audit`
- `memory`
- `rules`

辅助 skills：

- `docx`
- `pdf`
- `pptx`
- `xlsx`

skills 位于 `.agent_assets/skills/`，职责是提供领域上下文与工具使用约束，不直接承担业务执行。

## 编码要求

### 导入

- 使用绝对导入
- 标准库、三方库、自定义模块分组

### 类型注解

- 公共函数与方法必须有参数和返回值类型
- 可空类型使用 `Optional[T]`

### Docstring

- 所有公共函数必须有 docstring
- docstring 需说明用途、参数、返回值、异常

### 错误处理

- 禁止裸 `except`
- 业务错误用模块内自定义异常
- 不要吞掉底层错误，也不要泄露敏感信息

### 注释

- 注释解释设计意图、边界和业务原因
- 不写“给变量赋值”这类低价值注释

## 当前重点约束

- 保持代码高内聚、低耦合
- 每次只做可验证的小步重构
- 先读代码再改代码
- 写完代码必须补测试并重跑
- 完成后再做一次结构与安全视角检查
