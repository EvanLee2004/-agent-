# Agent 架构文档

财务助手 CLI 应用，多 Agent 协作模拟会计部门工作流程。

## 项目结构

```
.
├── main.py                 # CLI 入口
├── agents/                 # AI Agent（角色层）
│   ├── base.py            # Agent 基类（纯抽象接口）
│   ├── manager.py          # 协调者（意图分类 + 协调流程）
│   ├── accountant.py       # 执行者（记账执行）
│   └── auditor.py          # 审核者（审核执行）
├── core/                   # 核心基础设施
│   ├── llm.py             # LLM 客户端（中心化，返回 LLMResponse）
│   ├── models.py           # 模型配置（context_window 等）
│   ├── token_counter.py    # Token 计数器
│   ├── session.py          # 会话管理（多轮对话 + SQLite 持久化）
│   ├── compactor.py        # 上下文压缩器（95% 阈值触发）
│   ├── context.py          # 上下文构建（记忆注入 + 消息构建）
│   ├── memory.py           # Agent 记忆（JSON 持久化）
│   ├── ledger.py           # 账目数据库
│   ├── skill_loader.py     # Skill 加载器
│   └── schemas.py          # 数据结构
├── skills/                 # Skill 能力包
│   ├── coordination/       # 协调 Skill
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── intent.py
│   ├── accounting/         # 记账 Skill
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── execute.py
│   └── audit/              # 审计 Skill
│       ├── SKILL.md
│       └── scripts/
│           └── execute.py
├── memory/                 # Agent 记忆文件
├── sessions/              # 会话数据库
├── data/                  # 账目数据库
├── docs/                  # 架构文档
└── .env                   # 环境配置（换模型改这里）
```

## 架构原则

- **本质是提示词工程**：每个 Agent 的行为由 `SYSTEM_PROMPT` 决定
- **Skill 系统**：Skill = SKILL.md + scripts/，Skill 脚本不依赖 core/ 模块
- **多 Agent 协作**：Manager 协调，Accountant/Auditor 执行
- **自然语言交互**：LLM 返回文本而非 JSON
- **LLM 中心化**：Agent 统一调 LLM，Skill 只返回 prompt 数据
- **多轮会话**：支持会话持久化和上下文压缩（参考 OpenCode）

## Agent 职责

| Agent | 职责 | 使用 Skill | 记忆文件 |
|-------|------|-----------|---------|
| Manager | 意图分类，协调流程 | coordination | manager.json |
| Accountant | 记账执行，异常检测 | accounting | accountant.json |
| Auditor | 审核执行，问题标注 | audit | auditor.json |

## 核心模块

### `core/llm.py` - LLM 客户端

```python
@dataclass
class LLMResponse:
    content: str
    usage: dict  # {"prompt_tokens": x, "completion_tokens": y, "total_tokens": z}
    model: str

response = LLMClient.get_instance().chat(messages)
print(response.content)  # LLM 返回的文本
print(response.usage)   # Token 使用量
```

### `core/models.py` - 模型配置

```python
MODELS = {
    "MiniMax-M2.7": {"context_window": 204800, "max_tokens": 8192, ...},
    "gpt-4": {"context_window": 8192, "max_tokens": 2048, ...},
}

context_window = get_context_window()  # 自动读取 .env 中的 LLM_MODEL
```

换模型只需修改 `.env`：
```bash
LLM_MODEL=gpt-4
```

### `core/session.py` - 会话管理

```python
class ConversationSession:
    session_id: str
    messages: list[dict]      # 对话历史
    token_count: int           # 当前 token 估算
    summary: str | None       # 压缩后的摘要

session_manager = SessionManager()
session_id, messages = session_manager.get_or_create_session()
```

### `core/compactor.py` - 上下文压缩

参考 OpenCode 的做法：
- 阈值：context_window 的 **95%**
- 当 token 达到阈值时，调用 LLM 生成摘要
- 用摘要替换历史消息

```python
compactor = Compactor()
if compactor.should_compact(token_count):
    new_messages, summary = compactor.compact(messages)
```

### `core/token_counter.py` - Token 计数

```python
count = TokenCounter.estimate_from_text("中文 text")  # 估算
count = TokenCounter.from_api_response(usage)         # 从 API 响应提取
```

### `core/context.py` - 上下文构建

```python
messages = build_messages(
    system_prompt=agent.SYSTEM_PROMPT,
    task=user_input,
    session=conversation_session,
    memory_limit=20,  # 可配置的记忆数量
)
```

## Skill 系统

### Skill 目录结构

```
skills/<name>/
├── SKILL.md           # 元数据 + SYSTEM_PROMPT（必需）
├── scripts/           # 可执行脚本
│   ├── __init__.py
│   └── *.py          # 独立进程，通过 subprocess 调用
└── references/        # 参考文档
```

### SKILL.md 格式

```yaml
---
name: "accounting"
description: "记账技能..."
compatibility: "opencode"
version: "1.0.0"
---

# Accounting Skill

## SYSTEM_PROMPT

你是记账专家，负责...

## Capabilities

- execute: 执行记账
- detect_anomaly: 检测异常
```

### Skill 脚本独立性

**关键原则**：Skill 脚本完全独立，不依赖 core/ 模块，只返回 prompt 数据

```python
#!/usr/bin/env python3
"""Accounting Execute - 执行记账操作"""

def build_prompt(task: str, feedback: str = "") -> dict:
    # 只返回 prompt 数据，不调 LLM
    return {
        "system": SYSTEM_PROMPT,
        "prompt": PROMPT_TEMPLATE.format(task=task),
        "task": task,
        "feedback": feedback,
    }
```

## 工作流程

### 记账流程（Manager 协调）

```
用户输入记账任务
    ↓
Manager._classify_intent()
    ↓ Skill: coordination/intent.py
    ↓
┌─────────────────────────────────────────┐
│  循环最多 3 轮：                         │
│                                          │
│  Accountant.process(task)                 │
│      ↓  Skill: accounting/execute.py      │
│      ↓                                  │
│  Auditor.process(record)                  │
│      ↓  Skill: audit/execute.py          │
│      ↓                                  │
│  if 通过 → 返回结果                       │
│  else → Accountant.reflect(feedback)     │
│         修正后继续循环                   │
└─────────────────────────────────────────┘
```

### Skill 脚本调用

```python
result = SkillLoader.execute_script(
    "accounting",     # Skill 名称
    "execute",        # 脚本名称
    [task, "--json"], # 参数
)

messages = [
    {"role": "system", "content": result["data"]["system"]},
    {"role": "user", "content": result["data"]["prompt"]},
]
response = LLMClient.get_instance().chat(messages)
```

## 环境配置

`.env` 文件控制 LLM 配置，换模型只需修改这里：

```bash
LLM_PROVIDER=minimax
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.minimax.chat/v1
LLM_MODEL=MiniMax-M2.7
LLM_TEMPERATURE=0.3
```

## 记忆系统

每个 Agent 独立记忆 JSON 文件：

```json
{
  "agent": "accounting",
  "experiences": [
    {"context": "审核反馈: 金额过大需确认", "learned_at": "2026-04-01"}
  ]
}
```

## 扩展新 Agent

1. 在 `agents/` 下创建 Agent 类，继承 `BaseAgent`
2. 在 `skills/` 下创建对应 Skill 目录和 SKILL.md
3. 实现 `scripts/*.py` 脚本（独立，不依赖 core/）
4. 使用 `SkillLoader.load()` 加载系统提示词

```python
class Analyst(BaseAgent):
    NAME = "analysis"

    def __init__(self):
        skill = SkillLoader.load(self.NAME)
        self.SYSTEM_PROMPT = skill["system_prompt"]

    def process(self, task: str) -> str:
        result = SkillLoader.execute_script(
            self.NAME, "execute", [task, "--json"],
        )
        return result.get("message", str(result))
```

## 引用

本项目在设计与实现过程中参考了以下开源项目：

- **opencode** - AI 编程助手框架，提供了 Skill 系统和上下文压缩的设计思路  
  <https://github.com/anomalyco/opencode>
