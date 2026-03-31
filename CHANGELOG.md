# CHANGELOG

## 2026-04-01 - LLM 调用中心化重构（学 opencode）

### 依据

参考 opencode 的架构，LLM 调用应该中心化，Skill 只返回 prompt 数据。

### 核心变更

#### Skill 脚本改为只返回 prompt

Skill 脚本不再调用 LLM，只返回结构化 prompt 数据：

- `skills/coordination/scripts/intent.py` - 返回 `{"system", "prompt"}`
- `skills/accounting/scripts/execute.py` - 返回 `{"system", "prompt", "task", "feedback"}`
- `skills/audit/scripts/execute.py` - 返回 `{"system", "prompt", "record"}`

#### Agent 层统一调 LLM

Agent 负责调用 LLM：

- `agents/manager.py` - `_classify_intent()` 调 LLM
- `agents/accountant.py` - `process()` 调 LLM
- `agents/auditor.py` - `process()` 调 LLM

#### SkillLoader 返回格式统一

`SkillLoader.execute_script()` 返回：
- `{"status": "ok", "data": {...}}` - 脚本返回 dict
- `{"status": "ok", "message": str}` - 脚本返回 string

### 架构变化

| 方面 | 之前 | 现在 |
|------|------|------|
| LLM 调用 | Skill 各自调 | Agent 统一调 |
| Skill 职责 | 调 LLM + 返回结果 | 只返回 prompt |
| LLM 入口 | 分散 | **唯一**：LLMClient.chat() |

---

## 2026-04-01 - Skill 系统独立化重构（按 opencode 规范）

### 依据

Skill 脚本应该完全独立，不依赖 core/ 模块。参考 opencode 的 Skill 系统设计。

### 核心变更

#### Skill 目录重命名（避免与 Agent 名称混淆）

| 旧名称 | 新名称 |
|--------|--------|
| skills/manager/ | skills/coordination/ |
| skills/accountant/ | skills/accounting/ |
| skills/auditor/ | skills/audit/ |

#### Skill 脚本独立化

所有 Skill 脚本不再依赖 core/ 模块，只使用标准库：

- `skills/accounting/scripts/execute.py` - 规则内联
- `skills/audit/scripts/execute.py` - 规则内联
- `skills/coordination/scripts/intent.py` - LLM 直调

#### SkillLoader 支持环境变量

`SkillLoader.execute_script()` 新增 `env` 参数，通过 subprocess 传递给脚本：

```python
SkillLoader.execute_script(
    "accounting",
    "execute",
    [task, "--json"],
    env={"LLM_API_KEY": os.environ.get("LLM_API_KEY", "")},
)
```

#### Agent 层处理数据流

- `accountant.py` - 调用 Skill 获取记账数据，写入数据库
- `accountant.process()` - 支持 `--feedback` 参数实现循环修正
- 移除 `core/utils.py`（detect_anomaly 已内联到 Skill）

#### 环境配置结构

`.env` 支持灵活配置：

```bash
LLM_PROVIDER=minimax
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.minimax.chat/v1
LLM_MODEL=MiniMax-M2.7
LLM_TEMPERATURE=0.3
```

换模型只需修改 `.env`，无需改代码。

### 架构

```
Agent 层（业务逻辑）
├── Manager   → Skill: coordination
├── Accountant → Skill: accounting → 写 ledger.db
└── Auditor  → Skill: audit

Skill 层（纯计算，独立）
├── coordination/scripts/intent.py
├── accounting/scripts/execute.py  ← 规则内联，LLM 直调
└── audit/scripts/execute.py       ← 规则内联，LLM 直调
```

### 代码清理

- 移除 `skills/accountant/scripts/detect_anomaly.py`（重复代码）
- 移除 `core/utils.py`（备用代码）
- 移除 `agents/base.py` 中未使用的 `AuditResult` 导入
- import 移到模块级（不在方法内联）

---

## 2026-03-31 - Skill 系统骨架搭建（模仿 opencode）

### 依据

按照 opencode 的 Skill 系统规范搭建基础设施：
- Skill = SKILL.md + scripts/
- 通过 subprocess 调用独立脚本
- Agent 从 Skill 加载 SYSTEM_PROMPT

### 核心变更

#### 新增 `core/skill_loader.py`
- `SkillLoader.load()` - 加载 Skill，提取 SYSTEM_PROMPT
- `SkillLoader.execute_script()` - 通过 subprocess 执行脚本
- 支持 JSON 输出格式
- 异常处理和超时控制

#### 新增 `skills/accountant/`
- `SKILL.md` - 元数据 + SYSTEM_PROMPT
- `scripts/execute.py` - 记账执行脚本
- `scripts/detect_anomaly.py` - 异常检测脚本
- `references/` - 参考文档目录

#### 新增 `skills/auditor/`
- `SKILL.md` - 元数据 + SYSTEM_PROMPT
- `scripts/execute.py` - 审核执行脚本
- `references/` - 参考文档目录

#### 新增 `skills/manager/`（目录结构）
- `SKILL.md`（待完善）
- `references/` - 参考文档目录

#### 更新 `agents/accountant.py`
- 初始化时从 Skill 加载 SYSTEM_PROMPT
- `process()` 调用 `SkillLoader.execute_script()`

#### 更新 `agents/auditor.py`
- 初始化时从 Skill 加载 SYSTEM_PROMPT
- `process()` 调用 `SkillLoader.execute_script()`

#### 更新 `agents/base.py`
- 添加 `handle()` 方法（之前缺失导致 main.py 调用失败）

#### 更新 `clear_db.sh`
- 添加 `rm -f memory/*.json` 清除记忆

#### 新增架构文档
- `docs/opencode-architecture.md` - OpenCode 原生架构
- `docs/financial-assistant-architecture.md` - 我们项目的架构

### 目录结构

```
skills/
├── accountant/
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── execute.py
│   │   └── detect_anomaly.py
│   └── references/
├── auditor/
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── __init__.py
│   │   └── execute.py
│   └── references/
└── manager/
    ├── SKILL.md
    └── references/
```

### 下一步

- [ ] 完善 Manager Skill
- [ ] Agent 实际调用 Skill 脚本进行测试
- [ ] 端到端测试
- [ ] 异常处理完善

---

## 2026-03-31 - 简化架构：回归自然语言交互

### 依据

**本质是提示词工程**：Agent 的行为由 SYSTEM_PROMPT 决定，不应被固定的方法名束缚。

### 核心变更

#### 简化 `agents/base.py`
- 移除 `think()`、`_parse_thought()`、`reflect()` 等硬编码方法
- 移除 `execute()`、`build_messages()`、`read_rules()` 等
- 只保留核心方法：`call_llm()`、`update_memory()`、`ask_llm()`
- **本质**：`ask_llm()` 就是用提示词引导 LLM 推理

#### 简化 `agents/accountant.py`
- `process(task)` 用 `ask_llm()` 直接理解任务
- 用正则匹配代替 JSON 解析
- 保留 `_detect_anomaly()` 异常检测逻辑
- `reflect(feedback)` 简化为只记录记忆

#### 简化 `agents/auditor.py`
- `process(task)` 用 `ask_llm()` 直接审核
- 用正则匹配判断是否通过
- 移除 `_audit()` 内部方法

#### 简化 `agents/manager.py`
- `_classify_intent()` 用 `ask_llm()` 自然语言判断意图
- 移除 `ThoughtResult` 依赖
- `_handle_accounting()` 直接在 Manager 内循环

#### 删除 `core/workflow.py`
- 循环逻辑太简单，直接内联到 Manager

#### 简化 `core/schemas.py`
- 移除 `ThoughtResult`（不再需要）
- 只保留 `AuditResult`

### 设计理念

| 之前 | 之后 |
|------|------|
| 强制 LLM 返回 JSON | 直接用自然语言交互 |
| 多个固定方法（think/execute/reflect） | 一个 `ask_llm()` + 提示词模板 |
| 复杂的工作流类 | 简单直接的循环 |
| 结构化解析（JSON） | 简单的正则匹配 |

### Skill 系统准备

简化后的架构更利于 Skill 扩展：
- Skill 的提示词模板直接替换 `SYSTEM_PROMPT`
- Skill 的 Python 模块被 `process()` 调用
- 不再有硬编码的方法名限制

---

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
