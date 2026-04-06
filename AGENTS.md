# Agent 开发指南

本文档面向在本仓库中工作的 AI Agent。当前项目的核心目标不是“再造一个 Agent 框架”，而是**以 DeerFlow 作为底层 runtime 能力**，在本项目内实现一个可持续演进的**财务 Agent 部门**。  
DeerFlow 负责通用的 runtime / task / memory / stream / sandbox 能力；本项目负责财务业务规则、财务工具、角色目录、协作摘要投影、历史持久化，以及 CLI / API 产品边界。

## 当前阶段定位

- 产品定位：面向财务场景的多 Agent 部门，而不是通用聊天机器人
- 技术路线：**DeerFlow public client + 本项目自维护财务域逻辑**
- 当前协作策略：
  - 简单单步任务：协调角色直接调用财务工具
  - 复杂多步任务：先调用 `generate_fiscal_task_prompt`，再调用 DeerFlow `task(..., subagent_type="general-purpose")`
- 明确禁区：
  - 不回退到自研 runtime / ToolLoopService / llm 目录
  - 不恢复 legacy 协作工具 `collaborate_with_department_role`
  - 不恢复自研 `memory/` 目录
  - 不再使用旧的 `role_trace_summary_builder`，当前摘要收口在 `FinalReplySummaryBuilder`

## 快速命令

```bash
# 启动 CLI
python main.py

# 启动 API
uvicorn api.deerflow_app:app --host 0.0.0.0 --port 8000 --workers 1

# 配置 API Key
echo "MINIMAX_API_KEY=your_key" > .env

# 安装依赖
pip install -r requirements.txt

# 运行全部测试
./.venv/bin/python -B -m unittest discover -s tests -v

# 运行单个测试
./.venv/bin/python -B -m unittest tests.test_audit_service -v

# 清理数据库与记忆
./clear_db.sh
```

## 当前真实调用链

```text
CLI / API
  ↓
CliConversationHandler / AppConversationHandler
  ↓  （在 app 层打开 open_context_scope()，并做错误翻译）
ConversationRouter
  ↓
ConversationService
  ↓
FinanceDepartmentService
  ├─ DeerFlowDepartmentRoleRuntimeRepository
  │   ↓
  │ DeerFlowInvocationRunner
  │   ↓
  │ DeerFlowClient
  └─ CollaborationStepFactory + DepartmentWorkbenchService
      ↓
      execution_events → collaboration_steps → SQLite / 查询接口
```

关键事实：

- `conversation/` 是纯净层，不依赖 `runtime/deerflow/*`
- 请求级工具上下文由 `FinanceDepartmentToolContextRegistry.open_context_scope()` 在 `app/` 层管理
- `FinanceDepartmentService` 只负责“开启一回合财务部门协作”，不直接理解 DeerFlow 内部实现
- DeerFlow stream 事件先落成 `execution_events`，再由 `CollaborationStepFactory` 投影成用户可见的 `collaboration_steps`
- 最终回复摘要由 `department/workbench/final_reply_summary_builder.py` 收口，不再依赖旧的 trace summary 逻辑

## 目录与边界

- `app/`：启动入口与依赖装配。这里只负责工厂、bootstrap、请求作用域和错误翻译，不承载财务业务规则
- `api/`：FastAPI 对外接口与响应模型
- `conversation/`：会话边界与用户可见响应收口；保持纯净，不直接依赖 DeerFlow 适配层
- `department/`：财务部门主域
  - `roles/`：默认角色注册表与最小角色元数据
  - `collaboration/`：复杂任务 prompt 生成能力
  - `subagent/`：财务专业模式 prompt 构建
  - `workbench/`：协作步骤、执行事件、回合历史的投影与持久化
- `runtime/deerflow/`：DeerFlow 适配层，只做“把 DeerFlow 桥接到本项目”
- `vendor/deer-flow/`：以 git submodule 形式接入的 DeerFlow 上游源码，仅用于 editable install、烟雾测试和必要适配参考；**不是业务主接入路径**
- `accounting/`、`cashier/`、`audit/`、`tax/`、`rules/`：财务业务模块，内部遵循 `router → service → repository → model`
- `configuration/`：配置读取、校验和 provider 元数据
- `.agent_assets/deerflow_skills/`：DeerFlow 运行时可见的 skill 资产
- `.agent_assets/skills/`：本项目长期维护的领域技能资产
- `.runtime/deerflow/`、`.runtime/api/`：运行时生成目录，不提交到远端

## 当前角色体系

- `finance-coordinator`：入口角色，负责理解用户目标、判断是否直接用工具或进入复杂协作
- `finance-bookkeeping`：记账与凭证查询
- `finance-cashier`：资金收付事实记录与查询
- `finance-tax`：税额测算与税前准备
- `finance-audit`：凭证审核与风险识别
- `finance-policy-research`：规则与外部政策研究

入口角色必须唯一；当前默认入口角色是 `finance-coordinator`。

## 当前 DeerFlow 集成约束

### 只允许的接入方式

- 业务主路径只依赖 `deerflow.client.DeerFlowClient`
- 禁止 deep import DeerFlow 内部模块来拼装业务主链路
- `vendor/deer-flow/` 不作为会话主链路依赖注入点，除非任务明确要求修改 vendor 副本

### 当前已接入的财务工具

- `record_voucher`
- `query_vouchers`
- `record_cash_transaction`
- `query_cash_transactions`
- `calculate_tax`
- `audit_voucher`
- `reply_with_rules`
- `generate_fiscal_task_prompt`

### 当前同时暴露给 DeerFlow 的基础工具组

- `web_search`
- `web_fetch`
- `image_search`
- `ls`
- `read_file`
- `write_file`
- `str_replace`
- `bash`

### 运行时行为约束

- 每次角色回复前都要调用 `reset_agent()`
- 必须使用 `stream()` 收集完整事件流，不回退到 `chat()`
- 用户最终可见回复取**最后一个非空 AI 文本**
- `ExecutionEventType` 当前只认四类：`tool_call`、`tool_result`、`task_call`、`final_reply`
- `execution_events` 是内部遥测；`collaboration_steps` 是用户可见投影，二者不要混用

## 并发与运行时说明

- 请求级工具上下文使用 `ContextVar`，解决的是“工具上下文生命周期”问题
- DeerFlow 调用本身由 `DeerFlowInvocationRunner` 通过**进程级全局锁**串行保护
- `DeerFlowInvocationRunner` 同时做 `os.environ` 快照注入与恢复，但这只能缩小污染窗口，不能替代真正的跨进程并发隔离
- API 默认共享 `.runtime/api` 作为进程级 `runtime_root`
- 不同 `thread_id` 依赖 DeerFlow checkpoint 机制实现会话隔离
- `workbench.db` 在同一 `runtime_root` 下共享
- 当前部署建议固定为：`uvicorn --workers 1`

如果未来要做真正的并发扩展，优先考虑**进程隔离或独立 runtime_root 策略**，不要误以为 `ContextVar + env snapshot` 就已经具备完全并发安全。

## 业务能力现状

- `accounting/`：凭证记录、凭证查询、科目校验
- `cashier/`：资金收付记录、收付款查询、方向/金额/日期/账户校验
- `audit/`：凭证审核，覆盖借贷平衡、金额异常、摘要质量、重复入账、分录说明缺失
- `tax/`：当前仅支持小规模纳税人增值税、小型微利企业企业所得税基础测算
- `rules/`：基于本地规则文本构造规则参考，不直接替代财务工具执行

当前版本仍然是“财务操作与财务研究”的基础骨架，不是正式报税系统，也不是全自动财务 ERP。

## 配置约束

- 模型配置只支持 DeerFlow 风格的 `default_model + models[]`
- 不再支持历史单模型配置格式
- API Key 通过 `.env` 注入，如 `MINIMAX_API_KEY`
- `config.json` 中的 `deerflow_runtime` 是运行时唯一事实来源
- 当前默认配置：
  - `thinking_enabled = true`
  - `subagent_enabled = true`
  - `plan_mode = false`
  - `tool_search.enabled = false`

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

- **新增或修改的核心代码必须写详细中文注释**
- 注释重点解释：为什么这样设计、当前边界是什么、为什么不能简单化、与 DeerFlow 的协作点是什么
- 不写“给变量赋值”这类低价值注释
- 涉及并发、上下文作用域、事件投影、财务口径时，必须把设计原因讲清楚

### 命名

- 类名：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 私有成员：前缀 `_`

### 错误处理

- 禁止裸 `except`
- 禁止向用户暴露第三方 runtime 细节
- 业务错误使用模块内异常类
- app 层负责把异常翻译成 HTTP 错误或用户友好文本；不要把错误翻译逻辑下沉到 `conversation/`

## 组织原则

- 按功能模块组织，不按 `services/`、`infrastructure/` 等横切目录扩展
- `router → service → repository → model` 是默认分层顺序，禁止跨层直接调用
- 一个文件一个类是默认原则
- 禁止新增 `utils.py` / `helpers.py`
- 不要把第三方运行时细节渗透进 `conversation/` 或具体业务模块

## 测试要求

- 改业务逻辑，必须改对应测试
- 改 DeerFlow 接入层、角色目录、协作摘要链路时，优先回归：
  - `tests.test_architecture_constraints`
  - `tests.test_conversation_router_e2e`
  - `tests.test_deerflow_department_role_runtime_repository`
  - `tests.test_finance_department_assets_service`
  - `tests.test_request_level_context`
- 改 API 契约时，回归：
  - `tests.test_api_endpoints`
- 改财务专业 prompt / subagent 策略时，回归：
  - `tests.test_fiscal_prompt_builder_integration`
  - `tests.test_fiscal_role_prompt_builder`
- 改工作台摘要或回复压缩逻辑时，回归：
  - `tests.test_role_trace_summary_builder`
  - `tests.test_collaboration_step_formatter`
- 改 vendor 副本或沙箱相关代码时，回归：
  - `tests.test_vendor_deerflow_smoke`

推荐命令：

```bash
./.venv/bin/python -B -m unittest tests.test_architecture_constraints -v
./.venv/bin/python -B -m unittest tests.test_deerflow_department_role_runtime_repository -v
./.venv/bin/python -B -m unittest tests.test_request_level_context -v
```

## 文档同步规则

- 只要改了架构边界、工具目录、协作策略、并发模型或运行方式，必须同步检查：
  - `AGENTS.md`
  - `README.md`
  - `CLAUDE.md`
  - 对应测试断言
- 文档中不得声称：
  - `collaborate_with_department_role` 已从工具目录移除，不得声称其作为 legacy fallback 保留
  - 旧 `memory/` 目录仍是当前主路径
  - 旧 `role_trace_summary_builder` 仍在使用

## 当前阶段最重要的工程判断

- DeerFlow 是底座，不是产品本身；产品价值在财务部门抽象、角色边界和财务工具闭环
- `workbench` 的价值在于把 DeerFlow 原生事件投影成财务产品可展示、可审计的历史
- 当前并发策略是“**单进程内严格串行**”，不是通用高并发架构
- 任何新增能力都应优先复用现有角色目录、工具目录、工作台和配置工厂，不要平行造新入口
