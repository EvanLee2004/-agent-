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
│   └── schemas.py          # 数据结构（AuditResult）
├── agents/                 # AI 角色
│   ├── base.py            # Agent 基类（极度简化）
│   ├── manager.py          # 经理（意图分类 + 协调流程）
│   ├── accountant.py       # 会计（记账执行）
│   └── auditor.py          # 审核（审核执行）
├── memory/                 # Agent 记忆
├── rules/                  # 规则手册
├── data/                   # 运行时数据
├── sessions/               # 对话历史
├── skills/                 # Skill 区（未来扩展）
├── requirements.txt
└── .env
```

## 架构原则

- **本质是提示词工程**：Agent 的行为由 SYSTEM_PROMPT 决定
- **简单优先**：不过度设计，避免 YAGNIA
- **自然语言交互**：LLM 返回文本而非 JSON，不强制结构化
- **Skill 可替换**：Skill 系统可以替换 SYSTEM_PROMPT 来改变 Agent 行为

## Agent 职责

| Agent | 职责 | 读取规则 | 持有记忆 |
|-------|------|---------|---------|
| Manager | 意图分类、协调流程、汇总返回 | 否 | manager.json |
| Accountant | 记账执行、异常检测、接受反馈修正 | accounting_rules.md | accountant.json |
| Auditor | 审核执行、问题标注 | accounting_rules.md | auditor.json |

## 核心模块

### agents/base.py - Agent 基类

极度简化，只保留核心能力：

```python
class BaseAgent(ABC):
    NAME: str = ""
    SYSTEM_PROMPT: str = ""
    
    def call_llm(messages, temperature) -> str
    def update_memory(experience: str) -> None
    def ask_llm(task: str, context: str = "") -> str
    
    @abstractmethod
    def process(self, task: str) -> str
```

**关键设计**：
- `ask_llm()` - 构造消息并调用 LLM，自动注入记忆上下文
- `process()` - 抽象方法，子类实现业务逻辑
- 不再有 `think()`、`reflect()` 等硬编码方法

### agents/manager.py - 协调流程

```python
def process(task: str) -> str:
    intent = _classify_intent(task)  # LLM 判断意图
    if intent == "accounting":
        return _handle_accounting(task)
    elif intent == "review":
        return _handle_review()
    ...

def _handle_accounting(task: str) -> str:
    # 循环：Accountant 执行 → Auditor 审核 → 反思
    # 最多 3 轮
```

### agents/accountant.py - 记账执行

```python
def process(task: str) -> str:
    # 用 ask_llm() 提取记账信息
    # 写入 ledger.db
    # 返回记账结果

def reflect(feedback: str) -> None:
    # 将反馈记录到记忆
```

### agents/auditor.py - 审核执行

```python
def process(record: str) -> str:
    # 用 ask_llm() 审核记账记录
    # 返回审核结果
```

## 工作流程

### 记账流程（Manager 协调）

```
用户输入记账任务
    ↓
Manager.process() → _classify_intent() 意图分类（accounting）
    ↓
Manager._handle_accounting()
    ↓
┌─────────────────────────────────────────┐
│  循环最多 3 轮：                         │
│                                          │
│  Accountant.process(task)                 │
│      ↓                                  │
│  Auditor.process(record)                 │
│      ↓                                  │
│  if 通过 → 返回结果                       │
│  else → Accountant.reflect(feedback)    │
│         修正后继续循环                   │
└─────────────────────────────────────────┘
    ↓
Manager 汇总 → 返回用户
```

### 查询流程

```
用户："查看今天记账"
    ↓
Manager.process() → _classify_intent() 意图分类（review）
    ↓
Manager._handle_review() → 查询 ledger.db
    ↓
表格展示（异常标⚠️）
```

## 意图分类

Manager 用 LLM 分析用户意图（自然语言判断），分为：

| Intent | 说明 | 处理函数 |
|--------|------|---------|
| accounting | 记账请求 | _handle_accounting() |
| review | 查询请求 | _handle_review() |
| transfer | 转账请求 | _handle_transfer() |
| unknown | 无法理解 | 返回错误提示 |

## 账目数据库

```sql
CREATE TABLE ledger (
    id INTEGER PRIMARY KEY,
    datetime TEXT,
    type TEXT,              -- 收入/支出/转账
    amount REAL,
    description TEXT,
    recorded_by TEXT,        -- "accountant"
    status TEXT,             -- pending/approved/rejected
    anomaly_flag TEXT,       -- high/medium/low
    anomaly_reason TEXT,
    reviewed_by TEXT
);
```

## 记忆系统

每个 Agent 独立记忆 JSON 文件，记录经验而非日志。

```json
{
  "agent": "accountant",
  "last_updated": "2026-03-31",
  "experiences": [
    {"context": "审核反馈: 金额过大需确认", "learned_at": "2026-03-31"}
  ]
}
```

**更新时机：** Agent 收到反馈时调用 `update_memory()` 写入。

## Skill 区（未来扩展）

基于 Claude Code Skills 标准：

```
skills/
├── accountant/
│   ├── SKILL.md              # Skill 元数据 + SYSTEM_PROMPT
│   └── skills/
│       ├── detect_anomaly.py # 异常检测逻辑
│       └── auto_categorize.py # 自动分类逻辑
└── auditor/
    ├── SKILL.md
    └── skills/
        ├── flag_issue.py
        └── compliance_check.py
```

**本质**：Skill = 提示词模板（SKILL.md）+ 行为模块（skills/*.py）

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
- LLM 返回解析失败时要有降级处理

## 扩展新 Agent

1. 在 `agents/` 下创建新文件
2. 继承 `BaseAgent`
3. 实现 `process()` 方法
4. 在 `memory/` 下创建对应的 `.json` 文件

```python
from agents.base import BaseAgent

class Analyst(BaseAgent):
    NAME = "analyst"
    SYSTEM_PROMPT = "你是财务分析师..."

    def process(self, task: str) -> str:
        # 分析逻辑
        return self.ask_llm(f"分析：{task}")
```

## 数据结构

### AuditResult - 审核结果

```python
@dataclass
class AuditResult:
    passed: bool                    # 是否通过
    comments: str                   # 审核意见
    anomaly_flag: Optional[str]     # high / medium / low / None
    anomaly_reason: Optional[str]    # 异常原因
```
