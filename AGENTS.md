# Agent 架构文档

多 Agent 协作模拟真实财务部门工作流程的架构说明。

## 项目结构

```
.
├── main.py                 # CLI 入口
├── agents/                 # AI Agent
│   ├── base.py            # 异步 Agent 基类
│   ├── reception.py       # 财务专员（意图分类）
│   ├── manager.py         # 财务主管（协调）
│   ├── accountant.py      # 会计（执行）
│   └── auditor.py         # 审计（审核）
├── core/                   # 核心基础设施
│   ├── message_bus.py     # 异步消息总线
│   ├── llm.py            # LLM 客户端
│   ├── ledger.py          # 账目数据库
│   └── skill_loader.py    # Skill 加载器
├── skills/                # Skill 能力包
│   ├── coordination/      # 协调 Skill
│   ├── accounting/       # 记账 Skill
│   └── audit/           # 审计 Skill
├── memory/               # Agent 记忆
├── data/                 # 账目数据库
└── .env                  # 环境配置
```

## 架构设计

### 参考项目

本架构参考了以下优秀项目：

1. **[edict - 三省六部制](https://github.com/cft0808/edict)** (13.8k ⭐)
   - 多 Agent 协作的制度设计
   - 审核封驳机制
   - 实时看板

2. **[MetaGPT - 软件公司](https://github.com/FoundationAgents/MetaGPT)**
   - SOP 流程形式化
   - 角色分工协作

3. **[opencode](https://github.com/anomalyco/opencode)**
   - Skill 系统设计
   - 上下文压缩机制

### 角色对应关系

| 三省六部 | 财务部门 | 职责 |
|---------|---------|------|
| 太子 | 财务专员 | 用户入口，意图理解 |
| 尚书省 | 财务主管 | 任务协调，流程控制 |
| 户部 | 会计 | 具体执行 |
| 门下省 | 审计 | 审核把关，封驳权 |

## Agent 职责

| Agent | 职责 | 使用 Skill | 监听队列 |
|-------|------|-----------|---------|
| 财务专员 | 意图分类、闲聊处理 | coordination | 财务专员 |
| 财务主管 | 任务协调、结果汇总 | - | 财务主管 |
| 会计 | 执行记账、数据库操作 | accounting | 会计 |
| 审计 | 审核记账、封驳权 | audit | 审计 |

## 消息总线

### MessageBus - 异步消息传递

消息总线采用 Request-Reply 模式，支持广播和直接通信。

```python
@dataclass
class Message:
    id: str              # 消息唯一ID
    sender: str          # 发送者
    recipient: str       # 接收者，""表示广播
    content: str         # 内容
    msg_type: str       # task/result/approval/rejection/chat
    intent: str          # accounting/transfer/review/chat
    metadata: dict       # 附加数据
```

### 通信模式

```
用户 → 财务专员 → 财务主管 → 会计 ↔ 审计 → 财务主管 → 财务专员 → 用户
                         (按需直接通信)
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
  - 发给 → 会计（直接通信）
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

### agents/base.py - AsyncAgent 基类

```python
class AsyncAgent(ABC):
    def __init__(self, name: str, bus: Optional[MessageBus] = None):
        self.name = name
        self.bus = bus or MessageBus.get_instance()
        self._queue = self.bus.register(name)

    async def start(self):
        self._task = asyncio.create_task(self._loop())

    async def send_to(self, recipient: str, content: str, 
                      msg_type: str = "task", 
                      intent: str = "") -> Optional[Message]:
        msg = Message(sender=self.name, recipient=recipient, content=content)
        return await self.bus.send(msg)

    async def reply(self, original: Message, content: str):
        await self.bus.reply(original, content)
```

### core/message_bus.py - 消息总线

```python
class MessageBus:
    def register(self, name: str) -> asyncio.Queue
    async def send(self, msg: Message, timeout: float = 60.0) -> Optional[Message]
    async def reply(self, original: Message, content: str, msg_type: str = "result")
    async def broadcast(self, msg: Message, recipients: list[str])
    async def forward(self, msg: Message, to: str)
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

## 环境配置

`.env` 文件控制 LLM 配置：

```bash
LLM_PROVIDER=minimax
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.minimax.chat/v1
LLM_MODEL=MiniMax-M2.7
LLM_TEMPERATURE=0.3
```

## 用户输入格式

记账任务需要包含完整信息：

```
报销差旅费500元，日期2024-01-15，说明客户拜访交通费，发票已附
```

必需字段：
- **金额**：数字
- **类型**：收入/支出/转账（从上下文推断）
- **日期**：YYYY-MM-DD 格式
- **说明**：用途或来源
- **发票状态**（支出时）：已附/未附

## 扩展新 Agent

1. 在 `agents/` 下创建 Agent 类，继承 `AsyncAgent`
2. 在 `skills/` 下创建对应 Skill 目录和 `scripts/*.py`
3. 在 `handle()` 方法中处理消息并调用 `reply()` 回复

```python
class Analyst(AsyncAgent):
    def __init__(self, bus=None):
        super().__init__("分析师", bus)
        self.skill_name = "analysis"

    async def handle(self, msg: Message):
        result = await asyncio.to_thread(self._process, msg.content)
        await self.reply(msg, result)
```
