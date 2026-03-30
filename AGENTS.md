# Agent Coding Guidelines

财务助手 CLI 应用，多 Agent 协作模拟会计部门工作流程。

## 项目结构

```
.
├── main.py                 # CLI 入口
├── core/                   # 核心基础设施（与业务无关，可复用）
│   ├── llm.py             # LLM 调用
│   ├── session.py         # 对话历史管理（SQLite）
│   ├── memory.py          # 记忆读写（公用）
│   ├── rules.py           # 规则读取（公用）
│   └── ledger.py          # 账目数据库
├── agents/                 # AI 角色（业务逻辑）
│   ├── base.py            # Agent 基类（公共能力）
│   ├── manager.py         # 经理（协调流程、汇总返回）
│   ├── accountant.py      # 会计（记账）
│   └── auditor.py         # 审核（审查、标注问题）
├── memory/                 # Agent 记忆（各自读写）
│   ├── manager.json
│   ├── accountant.json
│   └── auditor.json
├── rules/                  # 人工维护的规则手册
│   └── accounting_rules.md # 记账守则
├── data/                   # 运行时数据
│   └── ledger.db          # 账目数据库
├── sessions/               # 对话历史
│   └── sessions.db
├── skills/                 # Skill 区（未来扩展）
├── requirements.txt
└── .env
```

## Agent 职责

| Agent | 职责 | 读取规则 | 持有记忆 |
|-------|------|---------|---------|
| Manager | 理解意图、协调流程、汇总返回用户 | 否 | manager.json |
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
以表格形式展示所有记录（异常标⚠️）
    ↓
用户指出问题 → 触发纠错流程
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

每个 Agent 有独立的记忆文件（JSON），记录"经验"而非日志。

```json
{
  "agent": "accountant",
  "last_updated": "2026-03-30",
  "experiences": [
    {
      "context": "报销差旅费>5000需预申请",
      "learned_at": "2026-03-28"
    }
  ]
}
```

**记忆更新时机：** 每次对话结束后，Agent 自己决定是否将新经验写入记忆。

**总结时机：** 当上下文 token 接近上限时，Agent 将旧记忆合并压缩。

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

## Build/Lint/Test Commands

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Application
```bash
source .venv/bin/activate
python main.py
```

## Code Style Guidelines

### Python Version
- Python 3.9+（使用 `Optional[X]` 而非 `X | None`）

### 类型提示
- 所有函数参数和返回值必须有类型提示
- 用 `Optional[X]` 而非 `X | None`
- 集合类型用 `list[X]`, `dict[X, Y]`

### 导入顺序
1. 标准库
2. 第三方库
3. 本地模块
空行分隔

### 命名规范
| 类型 | 规范 | 示例 |
|------|------|------|
| 类 | PascalCase | `LLMClient` |
| 函数/变量 | snake_case | `get_client` |
| 常量 | UPPER_SNAKE_CASE | `LEDGER_DB` |

### 错误处理
所有 API 调用和 I/O 操作必须包在 try/except 中。

### 文档
- 模块和公共函数用 docstring
- 注释说明"为什么"，不说明"是什么"

## 依赖

- `openai` - OpenAI SDK（兼容 MiniMax/DeepSeek API）
- `python-dotenv` - 环境变量加载

## 环境配置

复制 `.env.example` 到 `.env`，填入 API Key：
```
MINIMAX_API_KEY=your_key_here
```

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
