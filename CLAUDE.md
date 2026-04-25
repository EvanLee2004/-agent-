# CLAUDE.md

智能财务部门 — 面向小企业本地私有部署的多 Agent 财务后端。底层运行时使用 **crewAI**，会计、审核和出纳/银行业务逻辑由本项目自行维护。

## 架构摘要

```text
CLI (main.py) / API (api/accounting_app.py)
  ↓
AppConversationHandler / CliConversationHandler
  ↓
ConversationRouter
  ↓
ConversationService
  ↓
AccountingDepartmentService
  ├─ CrewAIAccountingRuntimeRepository → crewAI Crew
  └─ DepartmentWorkbenchService → SQLite workbench
```

## 关键边界

- `conversation/` 不依赖 crewAI。
- `runtime/crewai/` 是唯一运行时适配层。
- `accounting/`、`audit/` 和 `cashier/` 保存业务规则，不依赖 crewAI。
- 会计事实和银行流水以 SQLite 账簿为准，crewAI memory 默认开启但只用于受控会话上下文。
- API / CLI 错误翻译在 `app/` 层完成。

## 当前角色

| 角色 | 名称 | 职责 |
| --- | --- | --- |
| Manager | `accounting-manager` | 判断请求是否属于会计核算 |
| Accountant | `voucher-accountant` | 凭证录入、查账、科目查询 |
| Cashier | `cashier-agent` | 银行流水记录、查询和对账 |
| Reviewer | `ledger-reviewer` | 凭证复核和最终回复 |

## 当前工具

- `record_voucher`
- `query_vouchers`
- `audit_voucher`
- `query_chart_of_accounts`
- `record_bank_transaction`
- `query_bank_transactions`
- `reconcile_bank_transaction`

## 运行命令

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python main.py
./.venv/bin/python -m uvicorn api.accounting_app:app --host 0.0.0.0 --port 8000 --workers 1
./.venv/bin/python -B -m unittest discover -s tests -v
```

## 配置

`config.json` 使用：

- `default_model`
- `models[]`
- `crewai_runtime`

`crewai_runtime.process` 当前只支持 `sequential`。`memory_enabled` 默认开启，必须显式配置 `memory_storage_path` 和 `memory_embedding_provider=local_hash`；`cache_enabled` 默认关闭，避免有副作用工具被运行时缓存后复用。

## 维护规则

- 保持高内聚低耦合：业务逻辑在业务模块，运行时桥接在 `runtime/crewai/`。
- 新增核心代码必须有中文注释，解释设计原因、边界和与 crewAI 的协作点。
- 不新增横切 `utils.py` / `helpers.py`。
- 删除不在主路径内的旧模块，避免文档或测试继续暗示税务、报表或政策研究已经可用。
