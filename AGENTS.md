# Agent Coding Guidelines

财务助手 CLI 应用，多 Agent 协作模拟会计部门工作流程。

## 项目结构

```
.
├── main.py                 # CLI 入口
├── core/                   # 核心基础设施
│   ├── llm.py             # LLM 调用（单例模式）
│   ├── memory.py           # 记忆读写
│   ├── rules.py           # 规则读取
│   ├── ledger.py           # 账目数据库
│   ├── schemas.py          # 数据结构
│   ├── session.py          # 会话管理
│   └── skill_loader.py     # Skill 加载器
├── agents/                 # AI 角色（业务逻辑）
│   ├── base.py            # Agent 基类
│   ├── manager.py          # 协调者（意图分类 + 协调流程）
│   ├── accountant.py       # 执行者（记账执行）
│   └── auditor.py          # 审核者（审核执行）
├── skills/                 # Skill 系统（按 opencode 规范）
│   ├── coordination/       # 协调 Skill
│   │   ├── SKILL.md       # 元数据 + SYSTEM_PROMPT
│   │   └── scripts/
│   │       └── intent.py  # 意图分类
│   ├── accounting/         # 记账 Skill
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── execute.py  # 记账执行
│   └── audit/              # 审计 Skill
│       ├── SKILL.md
│       └── scripts/
│           └── execute.py  # 审核执行
├── memory/                 # Agent 记忆
├── rules/                  # 规则手册
├── data/                   # 运行时数据
├── sessions/               # 对话历史
├── docs/                   # 架构文档
│   └── opencode-architecture.md
├── requirements.txt
└── .env                    # 环境配置（换模型改这里）
```

## 架构原则

- **本质是提示词工程**：Agent 的行为由 SYSTEM_PROMPT 决定
- **Skill 系统**：模仿 opencode，Skill = SKILL.md + scripts/
- **多 Agent 协作**：Manager 协调，Accountant/Auditor 执行
- **自然语言交互**：LLM 返回文本而非 JSON
- **Skill 独立化**：Skill 脚本不依赖 core/，只用标准库
- **LLM 中心化**：Agent 统一调 LLM，Skill 只返回 prompt 数据

## Agent vs Skill

| 概念 | 说明 |
|------|------|
| Agent（角色） | 在 `agents/` 目录，负责业务逻辑（写库、流程控制、调用 LLM） |
| Skill（能力包） | 在 `skills/` 目录，被 Agent 调用，负责纯计算（返回 prompt 数据） |

## Agent 职责

| Agent | 职责 | 使用 Skill | 记忆文件 |
|-------|------|-----------|---------|
| Manager | 意图分类，协调流程 | coordination | manager.json |
| Accountant | 记账执行，异常检测 | accounting | accountant.json |
| Auditor | 审核执行，问题标注 | audit | auditor.json |

## 核心模块

### core/skill_loader.py - Skill 加载器

按 opencode 规范加载和管理 Skill：

```python
class SkillLoader:
    SKILLS_DIR = Path("skills")

    @classmethod
    def load(cls, skill_name: str) -> dict:
        """加载 Skill，返回 system_prompt 和路径"""

    @classmethod
    def execute_script(
        cls, skill_name: str, script_name: str, args: list, timeout: int, env: dict
    ) -> dict:
        """通过 subprocess 执行 Skill 脚本，env 传递环境变量"""
```

### agents/base.py - Agent 基类

极度简化，只保留核心能力：

```python
class BaseAgent(ABC):
    NAME: str = ""
    SYSTEM_PROMPT: str = ""

    def call_llm(messages, temperature) -> str
    def update_memory(experience: str) -> None
    def ask_llm(task: str, context: str = "") -> str
    def handle(task: str) -> str  # 调用 process

    @abstractmethod
    def process(self, task: str) -> str
```

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
│  else → Accountant.reflect(feedback)    │
│         修正后继续循环                   │
└─────────────────────────────────────────┘
```

### Skill 脚本调用

```python
# Agent 调用 Skill 脚本，获取 prompt 数据
result = SkillLoader.execute_script(
    "accounting",     # Skill 名称
    "execute",       # 脚本名称
    [task, "--json"], # 参数
)

# Agent 统一调 LLM
messages = [
    {"role": "system", "content": result["data"]["system"]},
    {"role": "user", "content": result["data"]["prompt"]},
]
response = LLMClient.get_instance().chat(messages)
```

## Skill 系统（模仿 opencode）

### Skill 脚本独立性

**关键原则**：Skill 脚本完全独立，不依赖 core/ 模块，只返回 prompt 数据

```python
#!/usr/bin/env python3
"""Accounting Execute - 执行记账操作"""

import argparse
import json

SYSTEM_PROMPT = "你是记账专家，负责..."
PROMPT_TEMPLATE = "从以下任务中提取记账信息：{task}..."

def build_prompt(task: str, feedback: str = "") -> dict:
    # 只返回 prompt 数据，不调 LLM
    return {
        "system": SYSTEM_PROMPT,
        "prompt": PROMPT_TEMPLATE.format(task=task),
        "task": task,
        "feedback": feedback,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--feedback", "-f", default="")
    args = parser.parse_args()

    result = build_prompt(args.task, args.feedback)

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result.get("message"))

if __name__ == "__main__":
    main()
```

## 环境配置

`.env` 文件控制 LLM 配置，换模型只需修改这里：

```bash
LLM_PROVIDER=minimax
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.minimax.chat/v1
LLM_MODEL=MiniMax-M2.7
LLM_TEMPERATURE=0.3
```

## 记忆系统

每个 Agent 独立记忆 JSON 文件：

```json
{
  "agent": "accounting",
  "last_updated": "2026-04-01",
  "experiences": [
    {"context": "审核反馈: 金额过大需确认", "learned_at": "2026-04-01"}
  ]
}
```

## 代码规范

### Python 版本
- Python 3.9+

### 类型提示
- 所有函数参数和返回值必须有类型提示
- 用 `Optional[X]` 而非 `X | None`

### 命名规范
| 类型 | 规范 | 示例 |
|------|------|------|
| 类 | PascalCase | `LLMClient` |
| 函数/变量 | snake_case | `get_client` |
| 常量 | UPPER_SNAKE_CASE | `LEDGER_DB` |
| dataclass | PascalCase | `AuditResult` |

### 错误处理
- 所有 API 调用和 I/O 操作必须包在 try/except 中
- subprocess 执行要有超时控制
- JSON 解析失败要有降级处理

## 扩展新 Agent

1. 在 `agents/` 下创建 Agent 类
2. 在 `skills/` 下创建对应 Skill 目录和 SKILL.md
3. 实现 `scripts/*.py` 脚本（独立，不依赖 core/）
4. 继承 `BaseAgent`，使用 `SkillLoader.load()`

```python
class Analyst(BaseAgent):
    NAME = "analysis"

    def __init__(self):
        skill = SkillLoader.load(self.NAME)
        self.SYSTEM_PROMPT = skill["system_prompt"]

    def process(self, task: str) -> str:
        result = SkillLoader.execute_script(
            self.NAME, "execute", [task, "--json"],
            env={"LLM_API_KEY": os.environ.get("LLM_API_KEY", "")},
        )
        return result.get("message", str(result))
```
