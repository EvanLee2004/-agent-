# CLAUDE.md

智能会计部门 — 面向小企业会计核算场景的多 Agent 系统。底层运行时使用 **crewAI**，会计业务逻辑由本项目自行维护。

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
- `accounting/` 和 `audit/` 保存业务规则，不依赖 crewAI。
- 会计事实以 SQLite 账簿为准，crewAI memory 默认关闭。
- API / CLI 错误翻译在 `app/` 层完成。

## 当前角色

| 角色 | 名称 | 职责 |
| --- | --- | --- |
| Manager | `accounting-manager` | 判断请求是否属于会计核算 |
| Accountant | `voucher-accountant` | 凭证录入、查账、科目查询 |
| Reviewer | `ledger-reviewer` | 凭证复核和最终回复 |

## 当前工具

- `record_voucher`
- `query_vouchers`
- `audit_voucher`
- `query_chart_of_accounts`

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

`crewai_runtime.process` 当前只支持 `sequential`。`memory_enabled` 和 `cache_enabled` 默认关闭，避免运行时记忆或缓存与 SQLite 会计事实冲突。

## 维护规则

- 保持高内聚低耦合：业务逻辑在业务模块，运行时桥接在 `runtime/crewai/`。
- 新增核心代码必须有中文注释，解释设计原因、边界和与 crewAI 的协作点。
- 不新增横切 `utils.py` / `helpers.py`。
- 删除不在主路径内的旧模块，避免文档或测试继续暗示旧能力仍存在。
