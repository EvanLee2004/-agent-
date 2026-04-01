# Agent 架构文档

财务助手 CLI 应用，多 Agent 协作模拟会计部门工作流程。

## 项目结构

```
.
├── main.py                 # CLI 入口（异步多轮会话）
├── agents/                 # AI Agent（异步消息处理）
│   ├── base.py            # AsyncAgent 基类
│   ├── manager.py          # 协调者（意图分类 + 协调流程）
│   ├── accountant.py       # 执行者（记账执行）
│   └── auditor.py          # 审核者（审核执行）
├── core/                   # 核心基础设施
│   ├── message_bus.py      # 异步消息总线
│   ├── llm.py             # LLM 客户端（中心化）
│   ├── ledger.py           # 账目数据库
│   ├── memory.py           # Agent 记忆
│   ├── session.py          # 会话管理
│   ├── compactor.py        # 上下文压缩器
│   ├── context.py          # 上下文构建
│   ├── token_counter.py    # Token 计数器
│   ├── models.py           # 模型配置
│   └── skill_loader.py     # Skill 加载器
├── skills/                 # Skill 能力包
│   ├── coordination/       # 协调 Skill
│   │   └── scripts/
│   │       └── intent.py
│   ├── accounting/         # 记账 Skill
│   │   └── scripts/
│   │       └── execute.py
│   └── audit/              # 审计 Skill
│       └── scripts/
│           └── execute.py
├── memory/                 # Agent 记忆文件
├── sessions/              # 会话数据库
├── data/                  # 账目数据库
└── .env                   # 环境配置
```

## 架构原则

- **消息总线架构**：Agent 通过异步消息总线通信，解耦各 Agent
- **异步处理**：所有 Agent 使用 asyncio 并发处理消息
- **Skill 系统**：Skill = SKILL.md + scripts/，Skill 脚本独立于 core/ 模块
- **自然语言交互**：LLM 返回文本而非 JSON
- **LLM 中心化**：Agent 统一调用 LLM，Skill 只返回 prompt 数据

## Agent 职责

| Agent | 职责 | 使用 Skill | 监听队列 |
|-------|------|-----------|---------|
| Manager | 意图分类，协调流程 | coordination | manager |
| Accountant | 记账执行，异常检测 | accounting | accountant |
| Auditor | 审核执行，问题标注 | audit | auditor |

## 核心模块

### `core/message_bus.py` - 异步消息总线

消息总线采用 Request-Reply 模式：

```python
@dataclass
class Message:
    sender: str
    recipient: str
    content: str
    reply_to: Optional[str] = None

# 注册 Agent 队列
queue = bus.register("accountant")

# 发送消息并等待回复
reply = await bus.send(Message(sender="manager", recipient="accountant", content="任务"))
```

### `agents/base.py` - AsyncAgent 基类

```python
class AsyncAgent(ABC):
    def __init__(self, name: str, bus: Optional[MessageBus] = None):
        self.name = name
        self.bus = bus or MessageBus.get_instance()
        self._queue = self.bus.register(name)

    async def start(self):
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            await self.handle(msg)

    async def send_to(self, recipient: str, content: str) -> Optional[Message]:
        msg = Message(sender=self.name, recipient=recipient, content=content)
        return await self.bus.send(msg)

    async def reply(self, original: Message, content: str):
        await self.bus.reply(original, content)
```

### `core/llm.py` - LLM 客户端

```python
@dataclass
class LLMResponse:
    content: str
    usage: dict
    model: str

response = LLMClient.get_instance().chat(messages)
```

## 工作流程

### 启动流程（main.py）

```
main.py 启动
    ↓
创建 MessageBus 单例
    ↓
创建 Manager/Accountant/Auditor 实例（共享 Bus）
    ↓
各 Agent 调用 start() 启动消息循环
    ↓
进入输入循环，等待用户输入
```

### 记账流程（Manager 协调）

```
用户输入记账任务
    ↓
Manager.handle() 接收消息
    ↓
Manager._classify() 意图分类（Skill: coordination/intent.py）
    ↓
意图为 "accounting"
    ↓
┌─────────────────────────────────────────┐
│  循环最多 2 轮：                         │
│                                          │
│  Manager → Accountant (send_to)          │
│      ↓ Skill: accounting/execute.py     │
│      ↓ LLM 提取记账信息                  │
│      ↓ 写入账目数据库                    │
│      ↓ reply() 返回记账结果              │
│                                          │
│  Manager → Auditor (send_to)             │
│      ↓ Skill: audit/execute.py          │
│      ↓ LLM 审核记账结果                  │
│      ↓ reply() 返回审核意见              │
│                                          │
│  if "通过" in 审核意见 → 返回成功        │
│  else 提取"请补充X" → 反馈给 Accountant │
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
4. 使用 `SkillLoader.load()` 加载系统提示词

```python
class Analyst(AsyncAgent):
    def __init__(self, bus=None):
        super().__init__("analyst", bus)
        self.skill_name = "analysis"
        skill = SkillLoader.load(self.skill_name)
        self.SYSTEM_PROMPT = skill["system_prompt"]

    async def handle(self, msg: Message):
        result = await asyncio.to_thread(self._process, msg.content)
        await self.reply(msg, result)
```

## 引用

- **opencode** - AI 编程助手框架，提供了 Skill 系统和上下文压缩的设计思路  
  <https://github.com/anomalyco/opencode>
