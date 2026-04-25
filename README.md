# 智能财务部门

面向小企业本地私有部署的多 Agent 财务后端。当前版本以 **crewAI** 作为底层运行时，本项目只维护会计业务规则、出纳/银行流水规则、工具边界、协作摘要投影、历史持久化，以及 CLI / API 产品边界。

## 产品边界

当前版本先做生产级会计内核，并提供出纳/银行流水的基础主链路：

- 凭证录入：`record_voucher`
- 凭证查询：`query_vouchers`
- 凭证复核：`audit_voucher`
- 凭证过账：`post_voucher`
- 凭证作废：`void_voucher`
- 凭证红冲：`reverse_voucher`
- 会计科目查询：`query_chart_of_accounts`
- 科目余额、明细账、试算平衡查询
- 银行流水记录：`record_bank_transaction`
- 银行流水查询：`query_bank_transactions`
- 银行流水对账：`reconcile_bank_transaction`

税务申报、权限系统、复杂现金流量表自动编制、政策研究和通用财务咨询不在当前版本主链路内。出纳模块只维护资金流水和对账状态，不直接篡改总账；需要生成凭证时必须通过会计工具完成。

## 架构

```text
CLI / API
  ↓
CliConversationHandler / AppConversationHandler
  ↓
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

关键原则：

- `conversation/` 是纯净层，不直接依赖 `runtime/crewai/*`。
- crewAI 负责 Agent/Task/Crew 编排和受控会话 memory，不保存权威财务事实。
- 会计事实、银行流水和审核状态以本项目 SQLite 仓储为准，涉及金额、科目、状态时必须调用工具确认。
- crewAI memory 默认开启，但只用于“刚才那张凭证”“上一笔流水”等上下文引用和偏好理解。
- SQLite 启动时执行 `schema_migrations` 幂等迁移，旧库会补齐会计期间、凭证生命周期和期间内凭证号。
- `execution_events` 是内部遥测，`collaboration_steps` 是用户可见历史。
- 固定采用 `Process.sequential`，保证“任务判断 → 会计执行 → 出纳执行 → 复核回复”的流程稳定可审计。

## 目录

```text
accounting/      会计科目、凭证录入与凭证查询
audit/           凭证审核
cashier/         银行流水记录、查询与对账
runtime/crewai/  crewAI 运行时适配层与工具包装器
department/      会计部门服务、角色目录与工作台
conversation/    会话边界与用户可见响应
app/             依赖装配、CLI/API 请求处理和启动初始化
api/             FastAPI 接口与响应模型
configuration/   模型池与 crewAI runtime 配置
tests/           单元测试与架构约束测试
```

## 运行

推荐使用 Homebrew `python@3.12`：

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

配置 API Key：

```bash
echo "MINIMAX_API_KEY=your_key" > .env
```

启动 CLI：

```bash
./.venv/bin/python main.py
```

启动 API：

```bash
./.venv/bin/python -m uvicorn api.accounting_app:app --host 0.0.0.0 --port 8000 --workers 1
```

运行测试：

```bash
./.venv/bin/python -B -m unittest discover -s tests -v
```

清理本地运行态：

```bash
./clear_db.sh
```

## 配置

`config.json` 使用 `default_model + models[] + crewai_runtime` 结构。`crewai_runtime` 只保留当前需要的最小开关：

```json
{
  "default_model": "minimax",
  "models": [
    {
      "name": "minimax",
      "provider": "minimax",
      "model": "MiniMax-M1",
      "base_url": "https://api.minimax.chat/v1",
      "api_key_env": "MINIMAX_API_KEY"
    }
  ],
  "crewai_runtime": {
    "process": "sequential",
    "memory_enabled": true,
    "memory_storage_path": ".runtime/crewai/memory",
    "memory_embedding_provider": "local_hash",
    "cache_enabled": false,
    "verbose": false
  }
}
```

## API

主要接口：

- `POST /api/accounting/{thread_id}/reply`
- `GET|POST /api/accounting/periods...`
- `POST /api/accounting/vouchers/{voucher_id}/post|void|reverse|correct`
- `GET /api/accounting/reports/account-balances`
- `GET /api/accounting/reports/ledger-entries`
- `GET /api/accounting/reports/trial-balance`
- `GET /api/accounting/integrity-check`
- `POST /api/accounting/bank-transactions/{transaction_id}/reconcile|unreconcile`
- `GET /api/accounting/bank-transactions/{transaction_id}/voucher-suggestion`
- `GET /api/accounting/{thread_id}/turns`
- `GET /api/accounting/{thread_id}/collaboration-steps`
- `GET /api/accounting/{thread_id}/events`
- `GET /health`

回复模型面向会计核算：

```json
{
  "reply_text": "...",
  "steps": [],
  "tool_results": [],
  "voucher_ids": [],
  "audit_summary": null,
  "context_refs": [],
  "errors": []
}
```

`voucher_ids`、`audit_summary`、`errors` 等结构化字段来自工具结果 envelope，不再从自然语言回复里正则提取。这样 API、CLI 和测试都走同一条后端链路。
