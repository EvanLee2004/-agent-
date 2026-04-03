# CHANGELOG

## 2026-04-03

### DeerFlow 底层接入

- 主会话运行时切换到 `DeerFlowClient`
- 新增 `DeerFlowDepartmentRoleRuntimeRepository`
- 新增 DeerFlow 运行时资产生成服务
- 新增 DeerFlow 客户端工厂
- 新增 DeerFlow 专用 skill 资产：
  - `.agent_assets/deerflow_skills/public/finance-core/SKILL.md`
  - `.agent_assets/deerflow_skills/public/coordinator/SKILL.md`
  - `.agent_assets/deerflow_skills/public/cashier/SKILL.md`
  - `.agent_assets/deerflow_skills/public/bookkeeping/SKILL.md`
  - `.agent_assets/deerflow_skills/public/policy-research/SKILL.md`
  - `.agent_assets/deerflow_skills/public/tax/SKILL.md`
  - `.agent_assets/deerflow_skills/public/audit/SKILL.md`

### 财务工具接入

- 把财务能力映射成 DeerFlow 可加载工具：
  - `collaborate_with_department_role`
  - `record_voucher`
  - `query_vouchers`
  - `record_cash_transaction`
  - `query_cash_transactions`
  - `calculate_tax`
  - `audit_voucher`
  - `store_memory`
  - `search_memory`
  - `reply_with_rules`

### 运行时收口

- 删除旧的自研 `ToolLoopService` 相关文件
- 删除旧 `llm/` 目录与自研聊天协议层
- 删除已失效的 `ToolDefinition` 协议残留
- 删除会话层里不该承载的财务工具上下文残留
- DeerFlow 运行目录收口到 `.runtime/deerflow/`
- 新增 `DEER_FLOW_HOME` 注入，避免 DeerFlow 状态写入用户主目录

### 财务部门角色化

- 新增 `department/` 模块
- 角色定义从单一目录表拆到 `department/roles/`
- 新增财务部门六角色目录：
  - `finance-coordinator`
  - `finance-cashier`
  - `finance-bookkeeping`
  - `finance-policy-research`
  - `finance-tax`
  - `finance-audit`
- 新增 DeerFlow 自定义 agent 资产生成服务
- 新增财务部门工具上下文注册器，隔离 DeerFlow 静态工具装配约束
- 新增共享工作台、角色协作服务和可见 trace 机制

### 产品化修正

- CLI 配置错误改为友好提示并退出，不再抛出 Python 栈
- 运行时失败不再把底层错误细节直接回显给最终用户
- `DependencyContainer` 去掉基于列表下标拼装 router 的实现

### 文档更新

- README 改写为当前 DeerFlow 财务部门阶段说明
- AGENTS 改写为当前真实开发约束
- 明确当前阶段已经落地角色目录和角色资产，下一步再打开角色协作

## 2026-04-02

### 之前阶段收口

- 删除旧的 `agents/`、`services/`、`infrastructure/`、`tools/`、`domain/`、`providers/`
- 重构为按功能模块组织的结构
- 主账收口到 `account_subject`、`journal_voucher`、`journal_line`
- 长期记忆统一写入 `MEMORY.md`
- 每日记忆统一写入 `memory/YYYY-MM-DD.md`
