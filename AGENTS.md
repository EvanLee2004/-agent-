# Agent 开发指南

本文档面向 AI Agent，为在此代码库中开发提供指导。

生成的代码要加详细注释。

## 项目概述

智能会计是一个单 Agent 系统，当前主架构为：

```text
用户
  ↓
AccountantAgent
  ↓
SkillPromptService（skills + 记忆 + 科目目录）
  ↓
ToolRuntime（原生 function calling）
  ↓
Tool Handlers
  ↓
Accounting / Tax / Audit / Memory Services
  ↓
SQLite 主账 + OpenClaw 风格记忆
```

主流程已经不再依赖“模型先输出结构化 JSON，再由本地解析执行”的旧链路。

## 运行命令

### 启动应用
```bash
python main.py
```

### 手动配置（如需要）
```bash
echo "LLM_API_KEY=your_key" > .env
python main.py
```

### OpenCode Skills
```bash
ls .opencode/skills
```

### 数据库与记忆清理
```bash
./clear_db.sh
```

### 依赖安装
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 测试
```bash
./.venv/bin/python -B -m unittest discover -s tests -v
```

## 当前架构要点

### 1. Agent 只做编排

- `agents/accountant_agent.py` 只负责：
  - 获取 system prompt
  - 调用 `ToolRuntime`
  - 返回最终回复
- Agent 不直接处理数据库细节，不再承担旧意图路由或 JSON 解析职责。

### 2. Skills 只负责领域上下文

- Skills 位于 `.opencode/skills/`
- Skills 的职责是：
  - 提供领域知识
  - 约束工具使用方式
  - 约束最终答复风格
- Skills 不再承担主流程协议输出，不要求模型手写 JSON。

### 3. Tool Runtime 是主执行入口

- `tools/runtime.py` 负责原生 function calling loop
- 第一轮强制至少调用一个工具
- 工具结果回灌给模型后，再生成最终中文答复
- 如果模型第一轮没有调用任何工具，主流程应视为失败，而不是悄悄退回自由聊天

### 4. 业务规则必须留在确定性服务层

- `services/accounting_service.py`：记账与凭证查询
- `services/tax_service.py`：税额确定性计算
- `services/audit_service.py`：凭证审核规则
- `services/memory_service.py`：记忆存储与检索
- 工具 handler 只做参数校验和服务调用，不承载核心业务规则

### 5. 主账是唯一业务真相

- 主账结构：
  - `account_subject`
  - `journal_voucher`
  - `journal_line`
- `infrastructure/ledger.py` 只是旧接口兼容层
- 不允许恢复主流程双写旧 `ledger`

## 代码风格

### 导入

- 使用绝对导入
- 三方库在前，标准库在中，自定义模块在后
- 每组之间空一行

### 类型注解

- 函数参数和返回值必须标注类型
- 使用 `Optional[T]` 表示可空类型，而非 `T | None`

### Docstrings

- 所有公共函数、公共类方法必须有 docstring
- docstring 要说明参数和返回值

### 注释

- 新增代码必须带详细中文注释
- 复杂控制流前要说明设计意图和边界
- 不要写“变量赋值”这种低价值注释

### 错误处理

- 使用明确异常类型，不捕获宽泛异常后静默吞掉
- 敏感信息不暴露在错误消息中
- Provider / tool 调用失败要给出明确、可定位的错误信息

### 异步

- 对外会话入口保持 `async/await`
- 不要把本地纯同步业务逻辑无意义地改成异步

## 项目结构

```text
├── main.py
├── bootstrap.py
├── agents/
│   ├── accountant_agent.py
│   └── factory.py
├── domain/
├── services/
├── infrastructure/
├── tools/
├── .opencode/
│   └── skills/
├── skills/                     # 仅保留文档处理类 helper scripts
├── MEMORY.md
├── memory/
├── tests/
├── opencode.json
└── config.json
```

## Skills

### 当前主技能

- `accounting`
- `tax`
- `audit`
- `memory`
- `rules`

### 文档处理类辅助技能

- `docx`
- `pdf`
- `pptx`
- `xlsx`

这些技能的 helper scripts 仍保留在根目录 `skills/` 下。

## 核心模块 API

### llm.py

- `LLMClient.get_instance()`
- `LLMClient.chat(...)`
- `LLMClient.chat_with_tools(...)`
- `LLMClient.require_native_tool_calling()`

### tools/

- `ToolRuntime`
- `ToolRegistry`
- `ToolDefinition`
- `ToolExecutionResult`

### accounting_repository.py

- `SQLiteChartOfAccountsRepository`
- `SQLiteJournalRepository`

### memory.py

- `OpenClawMemoryStore`
- `IAgentMemoryStore`
- `get_memory_store()`

## 业务规则

### 记账异常标注

- 金额 `> 50000`：标注“需审核”
- 金额 `< 10`：标注“金额过小”

### 税务默认规则

- `includes_tax=true` 只在用户明确说“含税”“价税合计”等时成立
- 若用户未明确说明含税，则默认 `includes_tax=false`

### 账目状态

- `pending`
- `approved`

## Git 约定

```text
.env
__pycache__/
*.pyc
.venv/
*.db
data/
sessions/
memory/*.md
.opencode/cache/*.sqlite
```
