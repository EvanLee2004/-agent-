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
│   └── ledger.py          # 账目数据库
├── agents/                 # AI 角色
│   ├── base.py            # Agent 基类
│   ├── manager.py         # 经理（协调流程）
│   ├── accountant.py      # 会计（记账）
│   └── auditor.py         # 审核（审查）
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
| Manager | 理解意图、协调流程、汇总返回 | 否 | manager.json |
| Accountant | 记账、讨论修改、标注异常 | accounting_rules.md | accountant.json |
| Auditor | 审核标注、通过/打回 | accounting_rules.md | auditor.json |

## 工作流程

### 记账流程
```
用户输入记账任务
    ↓
Manager 分配
    ↓
Accountant ← 读取 rules/accounting_rules.md
    ↓ 记账（写入 ledger.db，标注异常）
    ↓ 提交
Auditor ← 读取 rules/accounting_rules.md
    ↓ 审核
    ├─ 有问题 → 标注 → Accountant 修改 → 重审（最多3轮）
    └─ 通过
    ↓
Manager 汇总 → 返回用户
```

### 查询流程
```
用户："查看今天记账"
    ↓
Manager 查询 ledger.db
    ↓
表格展示（异常标⚠️）
    ↓
用户指出问题 → 触发纠错
```

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
    {"context": "报销差旅费>5000需预申请", "learned_at": "2026-03-28"}
  ]
}
```

**更新时机：** 对话结束后 Agent 自行决定是否写入。  
**总结时机：** 上下文 token 接近上限时压缩旧记忆。

## Skill 区（未来扩展）

```
skills/
├── manager/
│   ├── SKILL.md
│   └── skills/
│       ├── review_daily.py
│       └── generate_report.py
├── accountant/
│   ├── SKILL.md
│   └── skills/
│       ├── record.py
│       └── detect_anomaly.py
└── auditor/
    ├── SKILL.md
    └── skills/
        ├── review.py
        └── flag_issue.py
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

### 错误处理
所有 API 调用和 I/O 操作必须包在 try/except 中。

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
        pass
```
