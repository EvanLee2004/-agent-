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
│   ├── schemas.py          # 数据结构（AuditResult）
│   └── skill_loader.py     # Skill 加载器
├── agents/                 # AI 角色
│   ├── base.py            # Agent 基类
│   ├── manager.py          # 经理（意图分类 + 协调流程）
│   ├── accountant.py       # 会计（记账执行）
│   └── auditor.py          # 审核（审核执行）
├── skills/                 # Skill 系统（按 opencode 规范）
│   ├── accountant/
│   │   ├── SKILL.md       # 元数据 + SYSTEM_PROMPT
│   │   ├── scripts/       # 可执行脚本
│   │   │   ├── execute.py
│   │   │   └── detect_anomaly.py
│   │   └── references/
│   ├── auditor/
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   └── execute.py
│   │   └── references/
│   └── manager/
│       ├── SKILL.md
│       └── references/
├── memory/                 # Agent 记忆
├── rules/                  # 规则手册
├── data/                   # 运行时数据
├── sessions/               # 对话历史
├── docs/                   # 架构文档
│   ├── opencode-architecture.md
│   └── financial-assistant-architecture.md
├── requirements.txt
└── .env
```

## 架构原则

- **本质是提示词工程**：Agent 的行为由 SYSTEM_PROMPT 决定
- **Skill 系统**：模仿 opencode，Skill = SKILL.md + scripts/
- **多 Agent 协作**：Manager 协调，Accountant/Auditor 执行
- **自然语言交互**：LLM 返回文本而非 JSON

## Agent 职责

| Agent | 职责 | Skill | 持有记忆 |
|-------|------|-------|---------|
| Manager | 意图分类，协调流程 | manager | manager.json |
| Accountant | 记账执行，异常检测 | accountant | accountant.json |
| Auditor | 审核执行，问题标注 | auditor | auditor.json |

## 核心模块

### core/skill_loader.py - Skill 加载器

按 opencode 规范加载和管理 Skill：

```python
class SkillLoader:
    @classmethod
    def load(cls, skill_name: str) -> dict:
        """加载 Skill，返回 system_prompt 和路径"""
        
    @classmethod
    def execute_script(
        cls, skill_name: str, script_name: str, args: list, timeout: int
    ) -> dict:
        """通过 subprocess 执行 Skill 脚本"""
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
│   ├── execute.py      # 主执行脚本
│   └── *.py           # 其他脚本
└── references/        # 参考文档
```

### SKILL.md 格式

```yaml
---
name: "accountant"
description: "会计技能..."
compatibility: "opencode"
version: "1.0.0"
---

# Accountant Skill

## SYSTEM_PROMPT

你是财务会计，负责...

## Capabilities

- execute: 执行记账
- detect_anomaly: 检测异常
```

## 工作流程

### 记账流程（Manager 协调）

```
用户输入记账任务
    ↓
Manager.process() → 意图分类
    ↓
┌─────────────────────────────────────────┐
│  循环最多 3 轮：                         │
│                                          │
│  Accountant.process(task)                 │
│      ↓  SkillLoader.execute_script()      │
│  scripts/accountant/execute.py           │
│      ↓                                  │
│  Auditor.process(record)                 │
│      ↓                                  │
│  if 通过 → 返回结果                       │
│  else → Accountant.reflect(feedback)    │
│         修正后继续循环                   │
└─────────────────────────────────────────┘
```

### Skill 脚本调用

```python
# Agent 调用 Skill 脚本
result = SkillLoader.execute_script(
    "accountant",     # Skill 名称
    "execute",       # 脚本名称
    [task, "--json"], # 参数
)
```

## Skill 系统（模仿 opencode）

### scripts/execute.py 标准格式

```python
#!/usr/bin/env python3
"""Skill Execute - 功能描述"""

import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser(description="功能描述")
    parser.add_argument("task", help="任务描述")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()
    
    result = execute(args.task)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result.get("message", str(result)))

def execute(task: str) -> dict:
    """执行逻辑"""
    return {"status": "ok", "message": "..."}

if __name__ == "__main__":
    main()
```

## 记忆系统

每个 Agent 独立记忆 JSON 文件：

```json
{
  "agent": "accountant",
  "last_updated": "2026-03-31",
  "experiences": [
    {"context": "审核反馈: 金额过大需确认", "learned_at": "2026-03-31"}
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

1. 在 `agents/` 下创建新文件
2. 在 `skills/` 下创建对应目录和 SKILL.md
3. 实现 `execute.py` 等脚本
4. 继承 `BaseAgent`，使用 `SkillLoader.load()`

```python
class Analyst(BaseAgent):
    NAME = "analyst"
    
    def __init__(self):
        skill = SkillLoader.load(self.NAME)
        self.SYSTEM_PROMPT = skill["system_prompt"]
    
    def process(self, task: str) -> str:
        result = SkillLoader.execute_script(
            self.NAME, "execute", [task, "--json"]
        )
        return result.get("message", str(result))
```
