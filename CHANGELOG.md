# CHANGELOG - 架构重构

## 2026-03-30 - ReAct 架构改造

### 核心变更

#### 新增 `core/schemas.py`
- `ThoughtResult`: LLM 思考结果结构化返回
- `AuditResult`: 审核结果结构化返回

#### 改造 `agents/base.py`
- 新增 `think()` 方法：先用 LLM 分析任务，返回结构化 `ThoughtResult`
- 新增 `execute()` 方法：根据思考结果执行动作（子类实现）
- 新增 `reflect()` 方法：反思结果，接受反馈尝试修正
- 新增 `_parse_thought()` 解析方法

#### 改造 `agents/manager.py`
- 用 LLM 意图分类替代关键词匹配
- 智能路由：`accounting` / `review` / `transfer` / `unknown`
- `_handle_accounting()`: 最多3轮讨论循环

#### 改造 `agents/accountant.py`
- `execute()` 方法执行记账，写入数据库
- `reflect()` 方法记录审核反馈到记忆
- 保留异常检测逻辑

#### 改造 `agents/auditor.py`
- `execute()` 方法返回 `AuditResult` 结构化结果
- 重写 `think()` 方法针对审核场景

#### 更新 `AGENTS.md`
- 同步新架构文档
- 更新核心方法说明

### 技术细节

- **意图识别**: Prompt + JSON 解析（兼容性好）
- **ReAct 循环**: Accountant → Auditor → Accountant.reflect() 最多3轮
- **降级处理**: LLM 返回解析失败时有 fallback

### 下一步

- [ ] 实现 Skills 插件系统
- [ ] 端到端测试
- [ ] 清理 `agents/assistants/` 旧文件
