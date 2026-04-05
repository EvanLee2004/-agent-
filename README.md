# 智能财务部门

<p align="center">
  <img src="assets/readme-hero.svg" alt="智能财务部门项目封面图" width="100%" />
</p>

面向小企业财务场景的智能财务多 Agent 部门产品。当前版本以 **DeerFlow public client** 作为底层 agent runtime，并在本项目内保留财务业务规则、财务工具、协作摘要持久化以及 CLI / API 入口。  
系统的核心边界是：**DeerFlow 负责通用 runtime / task / memory / stream，本项目负责记账、审核、税务、出纳、规则问答和历史审计**。

## 开发与架构来源

- **Claude Code**
- **Codex**
- **DeerFlow**

## 当前能力

- **凭证记账**：把自然语言业务转换为标准会计凭证并入账
- **凭证查询**：按日期和状态检索历史凭证
- **资金事实管理**：记录和查询收款、付款、报销支付等出纳事实
- **税务测算**：支持小规模纳税人增值税、小型微利企业企业所得税基础测算
- **凭证审核**：支持金额异常、摘要质量、重复入账等规则审核
- **DeerFlow 原生记忆**：由 DeerFlow runtime 自动抽取事实并注入后续对话
- **规则问答**：支持基于项目规则和会计约束的说明性问答
- **协作摘要**：DeerFlow stream 事件驱动的多步协作摘要（工具调用 → 工具结果 → 最终结论），不暴露原始推理全文
- **多模型底层配置**：配置结构已经升级为 DeerFlow 风格 `default_model + models[]`

## 交付状态

当前版本已经完成：

- DeerFlow 公开嵌入客户端接入
- DeerFlow runtime 基础工具组接入
- DeerFlow 风格多模型配置落地
- DeerFlow client 运行时开关配置化
- 财务工具注册到 DeerFlow runtime
- DeerFlow skill 资产落地
- 财务部门六角色目录落地
- DeerFlow 自定义角色资产自动生成
- 协作主路径切换到 DeerFlow 原生 `task` / `subagent`
- 协作摘要基于 DeerFlow stream 事件落地
- FastAPI 多回合持久化与历史查询

当前版本**尚未**完成：

- 基于真实业务状态的复杂多角色协同策略
- 正式税务申报

## DeerFlow 能力状态

本节明确区分"刻意限制"和"尚未接入"的能力，避免给人"全能力等价 DeerFlow 官方"的错觉。

### 刻意限制（配置中已关闭，等待业务场景成熟）

| 能力 | 配置路径 | 当前值 | 原因 |
|------|----------|--------|------|
| `plan_mode` | `deerflow_runtime.client.plan_mode` | `false` | Plan mode 会强制启用 TodoList 中间件，适用于结构化规划场景。当前财务对话以记账/审核/税务为主，无需此能力。 |
| `tool_search` | `deerflow_runtime.tool_search.enabled` | `false` | 工具搜索允许模型自动从配置中发现和调用工具。当前财务工具集已由本项目明确注册，无需动态搜索。开启会增加延迟和不确定性。 |
| `MCP extensions` | `extensions_config.json` | 未配置 | `mcpServers` 为空。如需接入外部 MCP 服务（如飞书、云文档），需要在此配置。 |

### 尚未接入（代码层面未连接）

| 能力 | 状态 | 说明 |
|------|------|------|
| `stream artifacts` | 尚未收集 | `stream()` 返回的 `values` 事件中包含 `artifacts` 字段，当前代码仅保留注释扩展位，尚未实现收集。 |
| `uploads` | 未使用 | `DeerFlowClient.upload_files()` 等接口未接入，如需支持文件上传场景（如上传发票图片），需要单独实现路由。 |
| `checkpointer` 多实例隔离 | 进程内共享，session 间隔离 | API 层在同一进程内创建单一 factory 实例，runtime_root 固定为 `.runtime/api`。不同 thread_id 共享同一 config.yaml 和 workbench.db，但各自 checkpoint 目录隔离（由 DeerFlow runtime 实现）。**注意**：当前 API 是进程级单例，os.environ 快照恢复只缩小污染窗口，不保证多线程并发安全。推荐使用 `uvicorn --workers 1` 部署。 |

### 已正常接入的能力

| 能力 | 说明 |
|------|------|
| `thinking_enabled` | 模型扩展思考能力，已启用 |
| `subagent_enabled` | DeerFlow 原生 task 工具已启用；复杂多步任务通过 `generate_fiscal_task_prompt` + `task(..., subagent_type="general-purpose")` 两步流程完成 |
| `memory` | DeerFlow 原生记忆，每轮对话后自动提取事实并注入下一轮 system prompt |
| `stream()` | 正确使用 `stream()` 而非 `chat()`，保留完整事件流以支持 tool trace、usage、artifacts 等扩展，最终 reply 取最后一个非空 AI 文本 |
| `reset_agent()` | 每次 `reply()` 前调用，确保 memory/skills 上下文刷新 |

## 当前架构

```text
用户
  ↓
CLI / API（FastAPI）
  ↓
AppConversationHandler / CliConversationHandler（app 层：open_context_scope + 错误翻译）
  ↓
ConversationRouter（conversation 层：纯净，不含 runtime/deerflow 依赖）
  ↓
ConversationService（conversation 层：业务编排 + 响应清洗）
  ↓
FinanceDepartmentService
  ├─ DeerFlowDepartmentRoleRuntimeRepository → DeerFlowClient（reply_text / execution_events / usage）
  └─ CollaborationStepFactory + DepartmentWorkbenchService → SQLite 工作台（collaboration_steps / 历史回合）
  ↓
Feature Routers
  ↓
Feature Services
  ↓
SQLite 业务仓储 + DeerFlow Native Memory / Checkpointer
```

关键设计决策：

- **请求级工具上下文**：通过 `FinanceDepartmentToolContextRegistry.open_context_scope()` 在 `AppConversationHandler.handle()`（API）或 `CliConversationHandler.handle()`（CLI）中实现，作用域结束时自动释放，避免跨请求泄露
- **错误边界分层**：`ConversationRouter.handle()` 是纯净的，不捕获异常；`AppConversationHandler.handle()` 将异常翻译为 HTTP 400/500；`CliConversationHandler.handle()` 将异常翻译为用户友好中文文本
- **runtime_root 隔离级别**：API 进程内共享 `.runtime/api`，os.environ 快照恢复只缩小污染窗口，不保证多线程并发安全
- **两条 client 路径统一**：首次创建和缓存复用都必须在同一 `runtime_context.open_scope()` 中执行，确保 CURRENT_THREAD_ID 等上下文行为一致

关键原则：

- DeerFlow 只负责通用 agent runtime
- 财务业务规则仍由本项目自己维护
- 当前只依赖 DeerFlow 的**公开 client**，不依赖它的内部模块

## 项目结构

```text
├── main.py
├── app/                             # 启动入口与依赖装配
│   ├── conversation_request_handler.py  # API 请求处理器（open_context_scope + HTTP 错误翻译）
│   ├── cli_conversation_handler.py       # CLI 请求处理器（open_context_scope + 友好文本翻译）
│   ├── conversation_router_factory.py    # 会话主链路工厂
│   └── dependency_container.py          # 应用服务工厂
├── conversation/                    # 会话边界与用户可见响应收口（纯净层）
├── runtime/                         # 第三方运行时适配层（当前为 DeerFlow）
├── department/                      # 财务部门主域
│   ├── collaboration/               # 角色协作协议与协作工具
│   ├── roles/                       # 六个财务角色的独立定义
│   └── workbench/                   # 协作工作台：execution_events → collaboration_steps
├── accounting/                      # 记账与凭证查询
├── cashier/                         # 出纳事实与资金收付
├── audit/                           # 审核规则
├── tax/                             # 税务测算
├── rules/                           # 规则问答
├── configuration/                   # 配置读取与校验
├── .agent_assets/
│   ├── deerflow_skills/             # DeerFlow 运行期使用的 skill 资产
│   └── skills/                      # 本项目长期维护的领域 prompt 资产
├── MEMORY.md                        # 长期记忆
├── tests/
└── config.json
```

## 配置

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置模型与 DeerFlow runtime

准备 `.env`：

```bash
MINIMAX_API_KEY=your_key_here
# 可选：
# DEEPSEEK_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
```

准备 `config.json`：

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
    },
    {
      "name": "deepseek-research",
      "provider": "deepseek",
      "model": "deepseek-reasoner",
      "base_url": "https://api.deepseek.com/v1",
      "api_key_env": "DEEPSEEK_API_KEY"
    }
  ],
  "deerflow_runtime": {
    "client": {
      "thinking_enabled": true,
      "subagent_enabled": true,
      "plan_mode": false
    },
    "tool_search": {
      "enabled": false
    },
    "sandbox": {
      "use": "deerflow.sandbox.local:LocalSandboxProvider",
      "allow_host_bash": false,
      "bash_output_max_chars": 20000,
      "read_file_output_max_chars": 50000
    }
  }
}
```

如果你暂时只用一个模型，也建议仍然保持这个结构。这样后续切模型或按角色分配模型时，不需要再迁移配置格式。

### 3. 运行

```bash
python main.py
```

运行时会自动在 `.runtime/deerflow/` 下生成 DeerFlow 配置与状态目录；该目录为本地运行资产，已被忽略，不应提交到远端。

### 4. 启动 API 服务

```bash
uvicorn api.deerflow_app:app --host 0.0.0.0 --port 8000 --workers 1
```

推荐 `--workers 1`：当前 API 为进程级单例，os.environ 快照恢复只缩小污染窗口，不保证多 worker 并发安全。

**API 端点：**

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/conversations/{thread_id}/reply` | 处理用户输入，返回协作响应 |
| GET | `/api/conversations/{thread_id}/turns` | 获取线程全部历史回合（含每轮协作步骤） |
| GET | `/api/conversations/{thread_id}/collaboration-steps` | 获取全部回合的协作步骤（扁平列表） |
| GET | `/api/conversations/{thread_id}/events` | 获取内部执行事件（含 turn_index/event_sequence） |
| GET | `/health` | 健康检查 |

**并发安全说明：**
- API 是进程级单例，runtime_root 固定为 `.runtime/api`
- 不同 thread_id 共享同一 config.yaml 和 workbench.db
- DeerFlow checkpoint 目录通过 thread_id 在运行时自动隔离
- os.environ 快照恢复只保证"缩小污染窗口"，不保证多线程并发安全

## DeerFlow 接入方式

本项目当前通过 `DeerFlowClient` 接入 DeerFlow：

- 使用 DeerFlow 的公开嵌入客户端
- 使用 DeerFlow 的配置驱动工具加载
- 使用本项目自己的财务 tools 和业务 service

当前已接入的财务工具：

- `generate_fiscal_task_prompt`（为 DeerFlow task 生成结构化财务专业 prompt，coordinator 复杂任务专用）
- `record_voucher`
- `query_vouchers`
- `record_cash_transaction`
- `query_cash_transactions`
- `calculate_tax`
- `audit_voucher`
- `reply_with_rules`

当前同时开放的 DeerFlow 基础工具组包括：

- `web_search`
- `web_fetch`
- `image_search`
- `ls`
- `read_file`
- `write_file`
- `str_replace`
- `bash`

当前 DeerFlow skill 资产位于：

- `.agent_assets/deerflow_skills/public/finance-core/SKILL.md`
- `.agent_assets/deerflow_skills/public/coordinator/SKILL.md`
- `.agent_assets/deerflow_skills/public/cashier/SKILL.md`
- `.agent_assets/deerflow_skills/public/bookkeeping/SKILL.md`
- `.agent_assets/deerflow_skills/public/policy-research/SKILL.md`
- `.agent_assets/deerflow_skills/public/tax/SKILL.md`
- `.agent_assets/deerflow_skills/public/audit/SKILL.md`

## 记忆系统

- 运行时对话记忆由 DeerFlow 原生 memory 负责
- 事实会写入 `.runtime/deerflow/home/agents/<agent_name>/memory.json`
- 记忆注入由 DeerFlow system prompt 自动完成，不再通过 `store_memory` / `search_memory` 工具显式驱动
- 根目录 `MEMORY.md` 是项目工程长期记忆，不是产品运行时用户记忆

## 测试

```bash
./.venv/bin/python -B -m unittest discover -s tests -v
```

当前测试覆盖：

- DeerFlow 运行时资产生成
- 多模型配置加载与持久化
- 财务部门角色目录与角色资产生成
- DeerFlow public client 读取 skill
- DeerFlow 工具注册
- DeerFlow client 运行时开关透传
- 工作台持久化与协作摘要
- 记账与查账
- 资金收付记录与查询
- 税务测算
- 凭证审核
- DeerFlow 原生记忆配置注入
- DeerFlow stream 事件 → execution_events → collaboration_steps 全链路
- 会话边界与线程透传
- 多回合 SQLite 持久化（turns / collaboration_steps / execution_events）
- 幂等跟踪器会话级保护
- API 端点 HTTP 契约（reply/turns/collaboration-steps/events/health）
- `run_with_isolation` 环境变量快照恢复
- 两条 client 路径（首次创建 vs 缓存复用）runtime_context scope 统一

## 当前版本结论

- 已完成 DeerFlow 底层接入与多模型配置收口
- 已完成财务 tools 对接和 DeerFlow 原生 task 协作主路径
- 已完成财务部门角色注册、角色资产生成与工作台持久化
- 已保留会计业务核心在本项目内，由业务工具和业务仓储承担最终规则约束

## License

MIT
