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
│   ├── schemas.py          # 数据结构（ThoughtResult, AuditResult）
│   └── workflow.py         # ReAct 工作流（新增）
├── agents/                 # AI 角色
│   ├── base.py            # Agent 基类（简化后）
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

- **职责分离**：工作流逻辑抽离到 `core/workflow.py`
- **简单优先**：不过度设计，避免 YAGNIA
- **基础设施下沉**：`core/` 下的模块是通用能力
- **Agent 专注业务**：每个 Agent 只实现自己的业务逻辑

## Agent 职责

| Agent | 职责 | 读取规则 | 持有记忆 |
|-------|------|---------|---------|
| Manager | 意图分类、协调流程、汇总返回 | 否 | manager.json |
| Accountant | 记账执行、异常检测、接受反馈修正 | accounting_rules.md | accountant.json |
| Auditor | 审核执行、问题标注 | accounting_rules.md | auditor.json |

## 核心模块

### core/workflow.py - ReAct 工作流

将 ReAct 循环逻辑抽离出来，实现工作流与业务逻辑的分离：

```python
class ReActWorkflow:
    def __init__(self, agent: BaseAgent, auditor: Optional[Auditor] = None, max_rounds: int = 3)
    def run(self, task: str, hint: str = "") -> str
```

**工作流程：**
```
think() → execute() → (audit) → (reflect) → 循环
```

### agents/base.py - Agent 基类

只定义接口和公共工具方法：

```python
class BaseAgent(ABC):
    NAME: str = ""
    SYSTEM_PROMPT: str = ""
    
    # 工具方法
    def read_memory() -> dict
    def write_memory(memory: dict) -> None
    def update_memory(experience: str) -> None
    def read_rules(filename: str) -> str
    def call_llm(messages: list, temperature: float) -> str
    def build_messages(task: str, extra_context: str) -> list
    
    # ReAct 步骤
    def think(task: str, hint: str = "") -> ThoughtResult
    def reflect(result: str, feedback: str) -> str
    
    # 抽象方法
    def execute(plan: ThoughtResult, context: dict) -> str
    def process(task: str) -> str
```

## 工作流程

### 记账流程（Manager 协调）

```
用户输入记账任务
    ↓
Manager.process() → think() 意图分类（accounting）
    ↓
Manager._handle_accounting()
    ↓
ReActWorkflow.run() ← Accountant + Auditor
    ↓
┌─────────────────────────────────────────┐
│  循环最多 3 轮：                         │
│                                          │
│  Accountant.execute(thought)             │
│      ↓                                  │
│  Auditor._audit(thought, {record})     │
│      ↓                                  │
│  if passed → 返回结果                    │
│  else → Accountant.reflect(result, 反馈) │
│         修正后继续循环                   │
└─────────────────────────────────────────┘
    ↓
Manager 汇总 → 返回用户
```

### 查询流程

```
用户："查看今天记账"
    ↓
Manager.process() → think() 意图分类（review）
    ↓
Manager._handle_review() → 查询 ledger.db
    ↓
表格展示（异常标⚠️）
    ↓
用户指出问题 → 触发纠错
```

## 意图分类

Manager 用 LLM 分析用户意图，分为：

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
  "last_updated": "2026-03-30",
  "experiences": [
    {"context": "审核反馈: 金额过大需确认", "learned_at": "2026-03-30"}
  ]
}
```

**更新时机：** Agent 收到反馈时自动调用 `update_memory()` 写入。

## Skill 区（未来扩展）

基于 Claude Code Skills 标准：

```
skills/
├── manager/
│   ├── SKILL.md
│   └── skills/
│       ├── daily_report.py
│       └── generate_summary.py
├── accountant/
│   ├── SKILL.md
│   └── skills/
│       ├── detect_anomaly.py
│       └── auto_categorize.py
└── auditor/
    ├── SKILL.md
    └── skills/
        ├── flag_issue.py
        └── compliance_check.py
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
| dataclass | PascalCase | `ThoughtResult` |

### 错误处理
- 所有 API 调用和 I/O 操作必须包在 try/except 中
- LLM 返回解析失败时要有降级处理

## 扩展新 Agent

1. 在 `agents/` 下创建新文件
2. 继承 `BaseAgent`
3. 实现 `execute()` 和 `process()` 方法
4. 在 `memory/` 下创建对应的 `.json` 文件

```python
from agents.base import BaseAgent
from core.schemas import ThoughtResult

class Analyst(BaseAgent):
    NAME = "analyst"
    SYSTEM_PROMPT = "你是财务分析师..."

    def execute(self, plan: ThoughtResult, context: dict) -> str:
        # 分析逻辑
        ...

    def process(self, task: str) -> str:
        # 入口逻辑
        ...
```

## 数据结构

### ThoughtResult - LLM 思考结果

```python
@dataclass
class ThoughtResult:
    intent: str              # accounting / review / transfer / unknown
    entities: dict           # 提取的实体 {"amount": 500, "type": "支出"}
    reasoning: str           # 思考推理过程
    confidence: float = 1.0  # 置信度
```

### AuditResult - 审核结果

```python
@dataclass
class AuditResult:
    passed: bool                    # 是否通过
    comments: str                   # 审核意见
    anomaly_flag: Optional[str]     # high / medium / low / None
    anomaly_reason: Optional[str]    # 异常原因
```
