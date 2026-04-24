# 智能会计部门

面向小企业会计核算场景的多 Agent 系统。当前版本以 **crewAI** 作为底层运行时，本项目只维护会计业务规则、会计工具、协作摘要投影、历史持久化，以及 CLI / API 产品边界。

## 产品边界

当前版本只覆盖纯会计核算：

- 凭证录入：`record_voucher`
- 凭证查询：`query_vouchers`
- 凭证复核：`audit_voucher`
- 会计科目查询：`query_chart_of_accounts`

税务、出纳付款、政策研究和通用财务咨询不在当前版本主链路内。遇到这些请求时，会计部门应明确说明当前版本只支持会计核算，不假装处理。

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
  │ crewAI Crew / Agent / Task
  └─ CollaborationStepFactory + DepartmentWorkbenchService
      ↓
      execution_events → collaboration_steps → SQLite
```

关键原则：

- `conversation/` 是纯净层，不直接依赖 `runtime/crewai/*`。
- crewAI 只负责 Agent/Task/Crew 编排，不保存会计事实。
- 会计事实以本项目 SQLite 仓储为准，crewAI memory 初版关闭。
- `execution_events` 是内部遥测，`collaboration_steps` 是用户可见历史。
- 固定采用 `Process.sequential`，保证“判断任务 → 执行业务工具 → 复核回复”的流程稳定可审计。

## 目录

```text
accounting/      会计科目、凭证录入与凭证查询
audit/           凭证审核
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
      "api_key_env": "MINIMAX_API_KEY",
      "use": "crewai:LLM"
    }
  ],
  "crewai_runtime": {
    "process": "sequential",
    "memory_enabled": false,
    "cache_enabled": false,
    "verbose": false
  }
}
```

## API

主要接口：

- `POST /api/accounting/{thread_id}/reply`
- `GET /api/accounting/{thread_id}/turns`
- `GET /api/accounting/{thread_id}/collaboration-steps`
- `GET /api/accounting/{thread_id}/events`
- `GET /health`

回复模型面向会计核算：

```json
{
  "reply_text": "...",
  "steps": [],
  "voucher_ids": [],
  "audit_summary": null,
  "errors": []
}
```
