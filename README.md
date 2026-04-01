# 智能财务部门

多 Agent 协作模拟真实财务部门工作流程的 CLI 应用。

> 💡 本项目参考了 [edict 三省六部制](https://github.com/cft0808/edict) 的架构思想，但针对财务部门场景进行了优化。

## 角色

| 角色 | 职责 |
|------|------|
| **财务专员** | 理解用户意图、分类任务、处理闲聊 |
| **财务主管** | 协调任务流程、分发任务、汇总结果 |
| **会计** | 执行具体记账任务、数据库操作 |
| **审计** | 审核记账结果、封驳不合格条目 |

## 架构设计

### 核心思想

```
用户(客户) → 财务专员 → 财务主管 → 会计 ↔ 审计 → 财务主管 → 财务专员 → 用户
                         (循环协调，直到审核通过)
```

**与 edict 三省六部的对应关系**：

| 三省六部 | 财务部门 | 职责 |
|---------|---------|------|
| 太子 | 财务专员 | 用户入口，意图理解 |
| 尚书省 | 财务主管 | 任务协调，流程控制 |
| 户部 | 会计 | 具体执行 |
| 门下省 | 审计 | 审核把关，封驳权 |

### 通信模式

- **消息总线架构**：所有 Agent 通过 MessageBus 通信
- **按需直接通信**：Agent 之间可以在需要时直接通信（如审计封驳会计）
- **Request-Reply 模式**：发送消息并等待回复

### 参考架构

本项目参考了以下优秀项目：

1. **[edict - 三省六部制](https://github.com/cft0808/edict)** (13.8k ⭐)
   - 多 Agent 协作的制度设计
   - 审核封驳机制
   - 权限矩阵概念
   - 实时看板设计

2. **[MetaGPT - 软件公司](https://github.com/FoundationAgents/MetaGPT)**
   - SOP 流程形式化
   - 角色分工协作

3. **[opencode](https://github.com/anomalyco/opencode)**
   - Skill 系统设计
   - 上下文压缩机制

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 编辑 .env，填入你的 API Key
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.minimax.chat/v1
LLM_MODEL=MiniMax-M2.7
LLM_TEMPERATURE=0.3
```

### 3. 运行

```bash
python main.py
```

## 使用方式

```
你: 报销1000元差旅费，日期2024-01-15，说明客户拜访
助手: ✅ [ID:1] 支出 1000.0元 - 客户拜访差旅费

你: 查看账目
助手: ID   时间                 类型   金额       说明
      1    2024-01-15 10:00   支出   ¥1000.00   客户拜访差旅费
```

## 项目结构

```
├── agents/                 # AI Agent 代码
│   ├── base.py            # Agent 基类
│   ├── reception.py       # 财务专员（意图分类）
│   ├── registry.py        # 意图注册中心
│   ├── accountant.py      # 会计（执行）
│   └── auditor.py         # 审计（审核）
├── infrastructure/         # 基础设施
│   ├── message_bus.py     # 异步消息总线
│   ├── llm.py            # LLM 客户端
│   ├── ledger.py         # 账目数据库
│   └── skill_loader.py    # Skill 加载器
├── skills/                # Skill 能力包
│   ├── coordination/      # 协调 Skill
│   ├── accounting/        # 记账 Skill
│   └── audit/            # 审计 Skill
├── memory/               # Agent 记忆
├── data/                 # 账目数据库
└── .env                  # 环境配置
```

## 工作流程

### 记账流程

```
客户: "报销差旅费500元，日期2024-01-15"
    ↓
财务专员:
  - 理解意图 → 记账任务
  - 提取信息 → {金额:500, 类型:支出, 日期:2024-01-15}
  - 发给 → 财务主管
    ↓
财务主管:
  - 发给 → 会计 执行记账
    ↓
会计:
  - 执行 → 写入数据库
  - 返回 → "[ID:1] 支出 500元"
  - 发给 → 财务主管
    ↓
财务主管:
  - 发给 → 审计 审核
    ↓
审计:
  - 检查 → 发现缺少发票状态
  - 封驳 → "请补充发票状态"
  - 发给 → 会计（直接通信，不经过财务主管）
    ↓
会计:
  - 收到封驳 → 补充信息
  - 返回 → "[ID:1] 支出 500元, 发票已附"
    ↓
财务主管:
  - 发给 → 审计 再审
    ↓
审计:
  - 检查 → 通过
  - 准奏 → "审核通过"
    ↓
财务主管:
  - 汇总结果
  - 发给 → 财务专员
    ↓
财务专员:
  - 返回给客户 → "✅ 报销成功 [ID:1]"
```

## 核心模块

### MessageBus - 消息总线

```python
# 注册 Agent
queue = bus.register("accountant")

# 发送消息并等待回复
reply = await bus.send(Message(
    sender="reception",  # 财务专员
    recipient="accountant",
    content="任务内容"
))

# 直接回复
await bus.reply(original_msg, "回复内容")

# 转发消息
await bus.forward(msg, to="auditor")
```

### Agent 基类

```python
class AsyncAgent:
    async def start(self): ...
    async def stop(self): ...
    async def send_to(self, recipient: str, content: str) -> Message: ...
    async def reply(self, original: Message, content: str): ...
```

## Skill 系统

```
Skill = SKILL.md + scripts/*.py

skills/
├── coordination/
│   └── scripts/
│       └── intent.py     # 意图分类
├── accounting/
│   └── scripts/
│       └── execute.py    # 记账执行
└── audit/
    └── scripts/
        └── execute.py    # 审核执行
```

## 清除测试数据

```bash
./clear_db.sh
```

## 版本历史

- **v2.0** - 三省六部架构重构，引入财务专员、财务主管、审计封驳机制
- **v1.0** - 基础多 Agent 架构

## License

MIT
