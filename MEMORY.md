# 项目记忆

当前项目已经收敛为 **crewAI-first 智能财务部门后端**。

## 架构事实

- 主链路：`CLI/API → Handler → ConversationRouter → ConversationService → AccountingDepartmentService → CrewAIAccountingRuntimeRepository`
- 运行时适配层唯一入口：`runtime/crewai/`
- 财务事实来源：SQLite 账簿、银行流水表与工作台数据库
- crewAI memory：默认开启，但只用于受控会话上下文和偏好
- crewAI cache：默认关闭
- 流程：`Process.sequential`

## 当前工具

- `record_voucher`
- `query_vouchers`
- `audit_voucher`
- `query_chart_of_accounts`
- `record_bank_transaction`
- `query_bank_transactions`
- `reconcile_bank_transaction`

## 工程规则

- `conversation/` 保持纯净，不依赖运行时适配层
- `accounting/`、`audit/` 与 `cashier/` 保存业务规则，不直接依赖 crewAI
- 工具包装器只负责 crewAI 入参适配、上下文读取、事件记录和幂等保护
- 工作台保留 `execution_events` 与 `collaboration_steps` 两层模型，前者用于内部审计，后者用于用户展示
