# CHANGELOG

## 2026-03-31 - 架构重构：workflow.py 抽离

### 依据

职责分离原则：将 ReAct 循环逻辑从 Agent 抽离到 `core/workflow.py`

### 核心变更

#### 新增 `core/workflow.py`
- `ReActWorkflow` 类封装循环逻辑
- `run()` 方法：think → execute → audit → reflect 循环
- 最多 3 轮，审核通过或达到最大轮数退出

#### 简化 `agents/base.py`
- 移除 execute/reflect 的默认实现（改为抽象方法）
- 保留公共工具方法（call_llm, read_memory, build_messages 等）
- BaseAgent 只负责接口定义和公共能力

#### 更新 `agents/manager.py`
- `_handle_accounting()` 使用 `ReActWorkflow` 协调流程
- 职责更清晰：只做意图分类和路由

### 架构对比

| 之前 | 之后 |
|------|------|
| BaseAgent 包含 think/execute/reflect | BaseAgent 只定义接口 |
| Agent 内部管理 ReAct 循环 | ReActWorkflow 统一管理循环 |
| 职责不清 | 单一职责原则 |

### 下一步

- [ ] 实现 Skills 插件系统
- [ ] 单元测试
- [ ] 端到端测试

---

## 2026-03-31 - 代码规范重构

### 依据

按照 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) 重构代码。

### 改动

#### `core/schemas.py`
- 完善 docstrings，添加 Attributes 说明
- 保持现有数据结构不变

#### `agents/base.py`
- 完善所有函数的 docstrings
- 修正类型注解（`list[dict[str, str]]` 等）
- 改进注释格式

#### `agents/manager.py`
- 完善 docstrings
- 行长度控制在 80 字符内
- 移除无用的 `current_task` 变量

#### `agents/accountant.py`
- 完善 docstrings
- 将 `import json` 移到文件顶部
- 提取 `_extract_from_llm()` 辅助方法
- 行长度控制在 80 字符内

#### `agents/auditor.py`
- 统一 `execute()` 返回类型为 `str`（兼容基类）
- 新增 `_audit()` 内部方法返回 `AuditResult`
- 完善 docstrings

---

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
