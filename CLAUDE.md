# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

智能财务部门 — 面向小企业财务场景的多 Agent 系统（毕业设计）。底层 agent runtime 使用 **DeerFlow public client**，财务业务逻辑（记账、审核、税务、出纳）由本项目自行维护。

## Commands

```bash
# 启动 CLI
python main.py

# 运行全部测试
./.venv/bin/python -B -m unittest discover -s tests -v

# 运行单个测试模块
./.venv/bin/python -B -m unittest tests.test_audit_service -v

# 运行单个测试类
./.venv/bin/python -B -m unittest tests.test_conversation_router_e2e.TestConversationRouterE2E -v

# 清理数据库与记忆
./clear_db.sh

# 安装依赖
pip install -r requirements.txt
```

## Architecture

### 调用链路

```
CLI (main.py) / API (api/deerflow_app.py)
  ↓
AppConversationHandler / CliConversationHandler（app 层）
  ↓ open_context_scope() + 错误翻译
ConversationRouter（conversation 层：纯净，无 DeerFlow 依赖）
  ↓
ConversationService（conversation 层）
  ↓
FinanceDepartmentService
  ├─ DeerFlowDepartmentRoleRuntimeRepository → DeerFlowClient
  └─ CollaborationStepFactory + DepartmentWorkbenchService → SQLite
  ↓
Feature Routers → Feature Services → SQLite 业务仓储
```

### 分层规则

每业务模块遵循 `router → service → repository → model`，禁止跨层直接调用。

### 关键边界

| 目录 | 职责 |
|------|------|
| `api/` | FastAPI 入口，`POST /api/conversations/{thread_id}/reply` 等端点 |
| `app/` | 启动入口与依赖装配（DI 容器、工厂），具体实现和第三方接入只在此层装配 |
| `conversation/` | 会话边界，用户可见响应收口（纯净层，无 runtime/deerflow 依赖） |
| `department/` | 财务部门主域：角色注册表（`roles/`）、协作协议（`collaboration/`）、共享工作台（`workbench/`） |
| `runtime/deerflow/` | DeerFlow 适配层；静态配置事实来源在 `.agent_assets/deerflow_config/`，运行时状态写入 `.runtime/deerflow/` |
| `accounting/`, `cashier/`, `audit/`, `tax/`, `rules/` | 各业务特性模块，每个内部遵循 router/service/repository 分层 |
| `configuration/` | 配置读取与校验 |
| `.agent_assets/deerflow_skills/` | DeerFlow 运行期 skill 资产 |
| `.agent_assets/skills/` | 本项目领域 prompt 资产 |

### 六个财务角色

| 角色 | Agent Name | 职责 |
|------|------------|------|
| Coordinator | `finance-coordinator` | 入口角色，决策工具调用或复杂任务委派 |
| Cashier | `cashier` | 资金收付记录 |
| Bookkeeping | `bookkeeping` | 凭证记账 |
| Policy Research | `policy-research` | 政策研究 |
| Tax | `tax` | 税务测算 |
| Audit | `audit` | 凭证审核 |

## Critical Rules

1. **DeerFlow 只走公开入口** — 允许依赖 `deerflow.client.DeerFlowClient`，禁止 deep import DeerFlow 内部模块
2. **代码必须带详细中文注释** — 解释设计原因、边界和业务意图，不写低价值注释
3. **按功能模块组织** — 不按 `services/`, `infrastructure/` 等横切目录扩展；一个文件一个类；禁止新增 `utils.py` / `helpers.py`
4. **错误处理** — 禁止裸 `except`；禁止向用户暴露第三方 runtime 细节；业务错误使用模块内异常类
5. **每次改动必须可验证** — 先读代码再改，改完补测试或更新测试，完成后重跑测试
6. **使用绝对导入** — 标准库、三方库、自定义模块分组
7. **公共函数必须有类型注解和 docstring**
8. **禁止项** — 不要再造自研 runtime/ToolLoopService/llm 目录；不要把 `.runtime/` 提交到远端

### 请求级工具上下文

通过 `FinanceDepartmentToolContextRegistry.open_context_scope()` 在 `AppConversationHandler.handle()`（API）或 `CliConversationHandler.handle()`（CLI）中实现，作用域结束时自动释放，避免跨请求泄露。

### 错误翻译边界

- `ConversationRouter.handle()`：纯净层，不捕获异常
- `AppConversationHandler.handle()`：翻译为 HTTP 400（ConversationError）/ HTTP 500（DepartmentError）
- `CliConversationHandler.handle()`：翻译为用户友好中文文本

### DeerFlow 全局锁

`DeerFlowInvocationRunner` 使用 `threading.Lock` 类属性确保进程内 DeerFlow 调用串行化。

## API

- 启动：`uvicorn api.deerflow_app:app --host 0.0.0.0 --port 8000 --workers 1`
- 推荐 `--workers 1`：API 是进程级单例，os.environ 快照恢复仅缩小污染窗口，不保证多 worker 并发安全
- 端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/conversations/{thread_id}/reply` | 处理用户输入，返回协作响应 |
| GET | `/api/conversations/{thread_id}/turns` | 获取线程全部历史回合 |
| GET | `/api/conversations/{thread_id}/collaboration-steps` | 获取全部协作步骤（扁平列表） |
| GET | `/api/conversations/{thread_id}/events` | 获取内部执行事件（含 turn_index/event_sequence） |
| GET | `/health` | 健康检查 |

## Config

模型配置在 `config.json`，DeerFlow 风格 `default_model + models[]` 结构。API Key 通过 `.env` 注入（`MINIMAX_API_KEY` 等）。

### config.json 结构

```json
{
  "default_model": "minimax-main",
  "models": [
    {
      "name": "minimax-main",
      "provider": "minimax",
      "model": "MiniMax-M2.7",
      "base_url": "https://api.minimaxi.com/v1",
      "api_key_env": "MINIMAX_API_KEY"
    }
  ],
  "deerflow_runtime": {
    "client": { "thinking_enabled": true, "subagent_enabled": true, "plan_mode": false },
    "tool_search": { "enabled": false },
    "sandbox": { "use": "deerflow.sandbox.local:LocalSandboxProvider", ... }
  }
}
```

## DeerFlow 集成要点

- **stream() 而非 chat()**：保留完整事件流以支持 tool trace、usage、artifacts 等扩展，最终 reply 取最后一个非空 AI 文本
- **reset_agent()**：每次 `reply()` 前调用，确保 memory/skills 上下文刷新
- **runtime_root 隔离**：API 进程内共享 `.runtime/api`，CLI 使用 `.runtime/deerflow`，不同 thread_id 各自 checkpoint 目录隔离
- **两条 client 路径**：首次创建（`create_and_run_client()`）和缓存复用（`run_with_isolation()`）都必须在同一 `runtime_context.open_scope()` 中执行
- **DeerFlowInvocationRunner**：threading.Lock 确保进程内串行化，os.environ 快照恢复隔离环境变量

## 存储

- SQLite 业务仓储（凭证、资金、协作步骤）
- DeerFlow Native Memory/Checkpointer（`.runtime/deerflow/`）
