# CHANGELOG

## 2026-04-02

### 架构重构

- 删除旧的 `agents/`、`services/`、`infrastructure/`、`tools/`、`domain/`、`providers/`
- 重构为按功能模块组织的结构：
  - `app/`
  - `conversation/`
  - `accounting/`
  - `tax/`
  - `audit/`
  - `memory/`
  - `rules/`
  - `llm/`
  - `configuration/`
- 主链路切换为 `ConversationRouter -> ConversationService -> ToolLoopService`

### 工具调用

- 全面切换到原生 function calling
- 业务工具统一为：
  - `record_voucher`
  - `query_vouchers`
  - `calculate_tax`
  - `audit_voucher`
  - `store_memory`
  - `search_memory`
  - `reply_with_rules`
- 第一轮必须调用工具，禁止主流程退回自由聊天

### 账务模型

- 主账收口到 `account_subject`、`journal_voucher`、`journal_line`
- 删除旧 `ledger` 兼容代码
- 凭证入账、查询、审核都围绕主账模型运行

### 记忆系统

- 长期记忆统一写入 `MEMORY.md`
- 每日记忆统一写入 `memory/YYYY-MM-DD.md`
- SQLite FTS 只负责搜索索引，不再充当主存储
- 记忆召回场景增加一次受控纠偏，避免真实模型绕过 `search_memory`

### 仓库清理

- 删除历史数据和旧兼容逻辑
- 删除根目录 `skills/` 历史 helper 目录
- 更新 README、AGENTS 与测试到当前架构
