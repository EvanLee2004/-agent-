# Agent 开发指南

本文档面向在本仓库中工作的 AI Agent。当前项目目标是以 **crewAI** 作为底层运行时，实现一个边界清晰、可持续演进的**智能财务部门后端**。

crewAI 负责 Agent / Task / Crew / Memory 编排；本项目负责会计业务规则、出纳/银行流水规则、工具目录、角色目录、协作摘要投影、历史持久化，以及 CLI / API 产品边界。不要在本项目里再造通用 Agent 框架。

## 当前阶段定位

- 产品定位：小企业本地私有部署的智能财务部门，当前主路径是会计内核 + 出纳/银行基础能力
- 技术路线：crewAI runtime + 本项目自维护会计域逻辑
- 主流程：`Process.sequential`
- 记忆策略：crewAI memory 开启但受控，只用于会话上下文和偏好；会计事实、银行流水和审核状态以 SQLite 账簿/工具查询为准
- 明确禁区：
  - 不恢复旧税务、规则问答、政策研究或通用财务咨询主链路
  - 不新增平行 runtime 或自研 ToolLoop
  - 不把 crewAI 细节泄漏进 `conversation/` 或具体业务模块
  - 不允许出纳模块直接篡改总账；需要生成凭证时必须通过会计工具完成

## 快速命令

```bash
# 安装依赖
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt

# 启动 CLI
./.venv/bin/python main.py

# 启动 API
./.venv/bin/python -m uvicorn api.accounting_app:app --host 0.0.0.0 --port 8000 --workers 1

# 配置 API Key
echo "MINIMAX_API_KEY=your_key" > .env

# 运行全部测试
./.venv/bin/python -B -m unittest discover -s tests -v

# 清理数据库与运行态
./clear_db.sh
```

## 当前真实调用链

```text
CLI / API
  ↓
CliConversationHandler / AppConversationHandler
  ↓  （app 层打开 AccountingToolContextRegistry.open_context_scope()，并做错误翻译）
ConversationRouter
  ↓
ConversationService
  ↓
AccountingDepartmentService
  ├─ CrewAIAccountingRuntimeRepository
  │   ↓
  │ crewAI Crew / Agent / Task / Memory
  └─ CollaborationStepFactory + DepartmentWorkbenchService
      ↓
      execution_events → collaboration_steps → SQLite / 查询接口
```

关键事实：

- `conversation/` 是纯净层，不依赖 `runtime/crewai/*`
- 请求级工具上下文由 `AccountingToolContextRegistry.open_context_scope()` 在 `app/` 层管理
- `AccountingDepartmentService` 只负责开启一回合财务部门协作，不理解 crewAI 内部实现
- crewAI 工具包装器记录 `tool_call` / `tool_result`
- 固定任务投影为 `accounting_intake` / `accounting_execution` / `cashier_execution` / `accounting_review`
- `CollaborationStepFactory` 把内部事件投影成用户可见 `collaboration_steps`
- `tool_result` 必须是结构化 envelope，API 不再从自然语言回复里正则提取业务字段

## 目录与边界

- `app/`：启动入口与依赖装配，只负责工厂、bootstrap、请求作用域和错误翻译
- `api/`：FastAPI 对外接口与响应模型
- `conversation/`：会话边界与用户可见响应收口，保持纯净
- `department/`：会计部门主域、角色目录、工作台和协作步骤投影
- `runtime/crewai/`：crewAI 适配层，只做“把 crewAI 桥接到本项目”
- `accounting/`：会计科目、凭证记录、凭证查询
- `audit/`：凭证审核
- `cashier/`：银行流水记录、查询与对账，不直接修改总账
- `configuration/`：模型池、provider 元数据和 crewAI runtime 配置

## 当前角色体系

- `accounting-manager`：入口角色，判断请求是否属于会计核算
- `voucher-accountant`：凭证录入、凭证查询、会计科目查询
- `cashier-agent`：银行流水记录、查询和对账
- `ledger-reviewer`：凭证复核和最终回复

入口角色必须唯一；当前默认入口角色是 `accounting-manager`。

## 当前工具目录

- `record_voucher`
- `query_vouchers`
- `audit_voucher`
- `query_chart_of_accounts`
- `record_bank_transaction`
- `query_bank_transactions`
- `reconcile_bank_transaction`

工具包装器只放在 `runtime/crewai/`。具体业务规则仍在 `accounting/`、`audit/` 或 `cashier/`，遵循 `router → service → repository → model` 分层。

## 配置约束

- 模型配置只支持 `default_model + models[]`
- API Key 通过 `.env` 注入，如 `MINIMAX_API_KEY`
- `config.json` 中的 `crewai_runtime` 是运行时唯一事实来源
- 当前默认配置：
  - `process = sequential`
  - `memory_enabled = true`
  - `memory_storage_path = .runtime/crewai/memory`
  - `memory_embedding_provider = local_hash`
  - `cache_enabled = false`
  - `verbose = false`

## 代码风格

### 导入

- 使用绝对导入
- 分组顺序：标准库 → 三方库 → 自定义模块

### 类型注解

- 公共函数与方法必须声明参数和返回值类型
- 可空类型使用 `Optional[T]` 或 `T | None`

### Docstring

- 所有公共函数必须有 docstring
- 说明用途、参数、返回值、异常

### 注释

- 新增或修改的核心代码必须写详细中文注释
- 注释重点解释：为什么这样设计、当前边界是什么、为什么不能简单化、与 crewAI 的协作点是什么
- 不写“给变量赋值”这类低价值注释
- 涉及并发、上下文作用域、事件投影、会计口径时，必须把设计原因讲清楚

### 命名

- 类名：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 私有成员：前缀 `_`

### 错误处理

- 禁止裸 `except`
- 禁止向用户暴露第三方 runtime 细节
- 业务错误使用模块内异常类
- app 层负责把异常翻译成 HTTP 错误或用户友好文本

## 组织原则

- 按功能模块组织，不按 `services/`、`infrastructure/` 等横切目录扩展
- `router → service → repository → model` 是默认分层顺序，禁止跨层直接调用
- 一个文件一个类是默认原则
- 禁止新增 `utils.py` / `helpers.py`
- 不要把第三方运行时细节渗透进 `conversation/` 或具体业务模块

## 测试要求

- 改业务逻辑，必须改对应测试
- 改 crewAI 接入层、角色目录、协作摘要链路时，优先回归：
  - `tests.test_architecture_constraints`
  - `tests.test_crewai_accounting_runtime_repository`
  - `tests.test_crewai_accounting_tools`
  - `tests.test_request_level_context`
- 改 API 契约时，回归：
  - `tests.test_api_endpoints`
- 改工作台摘要或回复压缩逻辑时，回归：
  - `tests.test_collaboration_step_formatter`
  - `tests.test_final_reply_summary_builder`

## 文档同步规则

只要改了架构边界、工具目录、协作策略、并发模型或运行方式，必须同步检查：

- `AGENTS.md`
- `README.md`
- `CLAUDE.md`
- 对应测试断言

文档中不得声称旧财务部门、税务、规则问答、政策研究或报表模块仍是当前主路径。
文档可以说明当前出纳/银行模块是新主路径，但必须同时说明它只维护资金流水和对账状态，不直接改总账。
