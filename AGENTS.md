# Agent Coding Guidelines

财务助手 CLI 应用，多 Agent 协作模拟会计部门工作流程。

## 项目结构

```
.
├── main.py                 # CLI 入口
├── core/                   # 核心基础设施
│   ├── llm.py             # LLM 调用（单例模式）
│   ├── session.py         # 对话历史（SQLite）
│   ├── memory.py          # 记忆读写
│   ├── rules.py           # 规则读取
│   ├── ledger.py          # 账目数据库
│   └── schemas.py         # 数据结构（ThoughtResult, AuditResult）
├── agents/                 # AI 角色
│   ├── base.py            # Agent 基类（think/execute/reflect）
│   ├── manager.py         # 经理（意图分类 + 协调流程）
│   ├── accountant.py      # 会计（记账执行）
│   └── auditor.py         # 审核（审核执行）
├── memory/                 # Agent 记忆
│   ├── manager.json
│   ├── accountant.json
│   └── auditor.json
├── rules/                  # 规则手册
│   └── accounting_rules.md
├── data/                   # 运行时数据
│   └── ledger.db
├── sessions/               # 对话历史
│   └── sessions.db
├── skills/                 # Skill 区（未来扩展）
├── requirements.txt
└── .env
```

## Agent 职责

| Agent | 职责 | 读取规则 | 持有记忆 |
|-------|------|---------|---------|
| Manager | 意图分类、协调流程、汇总返回 | 否 | manager.json |
| Accountant | 记账执行、异常检测、接受反馈修正 | accounting_rules.md | accountant.json |
| Auditor | 审核执行、问题标注 | accounting_rules.md | auditor.json |

## 核心方法（ReAct 模式）

每个 Agent 继承 BaseAgent，拥有以下方法：

```python
class BaseAgent(ABC):
    def think(self, task: str, hint: str = "") -> ThoughtResult:
        """先思考：用 LLM 分析任务，返回结构化结果"""
        
    def execute(self, plan: ThoughtResult, context: dict) -> str:
        """根据思考结果执行动作（子类实现）"""
        
    def reflect(self, result: str, feedback: str) -> str:
        """反思结果，如有反馈则尝试修正"""
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

## 工作流程

### 记账流程（ReAct 循环）

```
用户输入记账任务
    ↓
Manager.think() → 意图分类（accounting）
    ↓
Manager 路由到 _handle_accounting()
    ↓
┌─────────────────────────────────────────┐
│  循环最多 3 轮：                         │
│                                          │
│  Accountant.execute(thought)             │
│      ↓                                  │
│  Auditor.execute(thought, {record})     │
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
Manager.think() → 意图分类（review）
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

**更新时机：** 对话结束后 Agent 自行决定是否写入。

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
3. 实现 `execute()` 方法
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
```
