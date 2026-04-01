# 多 Agent 通信架构研究

## 1. 当前架构问题

### 现有流程

```
用户输入
    ↓
Manager.process(task)  ← 意图分类 + 协调全在里面
    ↓
Accountant.process(task)  ← 直接调用
    ↕
Auditor.process(result)  ← 直接调用
    ↓
返回结果
```

### 发现的问题

| 问题 | 说明 |
|------|------|
| **紧耦合** | Agent 之间直接调用，不知道彼此存在 |
| **职责过重** | Manager 既做裁判又做选手 |
| **硬编码循环** | Accountant↔Auditor 循环是 if/else 写的 |
| **无消息协议** | Agent 间没有结构化通信 |
| **难以扩展** | 加新 Agent 需要改 Manager 代码 |

---

## 2. 消息总线 vs Actor 模型对比

| 维度 | B. 消息总线 | C. Actor 模型 |
|------|-------------|---------------|
| **耦合度** | 极低（只和 Bus 通信） | 低（直接消息传递，封装状态） |
| **通信效率** | 中（多一跳） | 高（直接传递） |
| **延迟** | 略高 | 低 |
| **消息顺序** | 需额外处理 | Actor mailbox 天然顺序 |
| **同步/异步** | 天然异步 | 天然异步 |
| **扩展性** | 极易 | 中 |
| **复杂度** | 中（需 broker） | 中（概念简单） |
| **适用规模** | 大规模、分布式 | 中小规模 |

### 选择：B（消息总线）

原因：
- 更松的耦合
- 更易扩展（加 Agent 只需改订阅）
- 适合未来扩展成分布式

---

## 3. 内存消息总线 vs Redis

| 因素 | 内存实现 | Redis |
|------|---------|-------|
| **规模** | 3-5 个 Agent，同进程 | 跨机器分布式 |
| **持久化** | 消息随进程消失 | 可持久化 |
| **失败恢复** | 无 | 消息确认 + 持久化 |
| **网络** | 同进程 | 跨网络通信 |
| **复杂度** | 简单，无需依赖 | 需要 Redis 服务 |

**结论**：当前选**内存实现**，但接口设计考虑未来迁移到 Redis。

---

## 4. 任务完成通知模式

| 模式 | 机制 | 复杂度 | 响应性 | 资源占用 |
|------|------|--------|--------|---------|
| **轮询** | 定期检查 | 低 | 低 | 中 |
| **回调** | 注册回调函数 | 中 | 高 | 低 |
| **Future** | 等待结果 | 中 | 高 | 低 |
| **Async Queue** | 阻塞等待队列 | 中 | 最高 | 最低 |

**结论**：选 **async/await + asyncio.Queue**（消息总线自带）。

---

## 5. 错误处理模式

### 需要处理的错误场景

| 场景 | 当前行为 | 应该行为 |
|------|---------|---------|
| Agent 崩溃 | 消息丢失，调用方挂起 | 检测超时，重试或 DLQ |
| 消息超时 | 返回错误字符串 | 指数退避重试，然后 DLQ |
| 发给不存在的 Agent | 静默失败 | 错误回调，断路器 |
| LLM API 失败 | 返回错误字符串 | 断路器保护 |

### 断路器模式

```
CLOSED ──(失败次数>=阈值)──> OPEN
  ↑                              │
  │                        (超时后)
  │                              v
  │                         HALF_OPEN
  │                              │
  └────────────(成功)────────────┘
```

### 死信队列（DLQ）

失败的消息进入 DLQ，支持：
- 持久化存储
- 手动重试
- 自动清理过期消息

---

## 6. 目标架构

```
用户 ←→ Manager（对话入口，唯一和用户交互）
            ↓
         Message Bus（通信中枢）
            ↓
    ┌───────┼───────┐
    ↓       ↓       ↓
Accountant  Auditor  (Future: Analyst)
    ↑_______↓_______↑
         Bus 通信
```

### 消息结构

```python
@dataclass
class Message:
    id: str                    # 唯一消息 ID
    type: str                 # task | reply | error | ack
    sender: str               # 发送者
    recipient: str            # 接收者，"" 表示广播
    content: str              # 消息内容
    reply_to: str | None      # 关联的消息 ID（请求/响应匹配）
    timestamp: datetime
    metadata: dict            # 附加数据（轮次等）
    max_retries: int          # 最大重试次数
    timeout_seconds: float    # 超时时间
```

### 工作流程

```
用户: "报销1000元差旅费"
    ↓
[1] Manager 收到消息
    ↓
[2] Manager → Bus("intent.classify") → Manager
    ↓ (意图分类)
[3] Manager → Bus("accounting.execute", reply_to=msg_id)
    ↓
[4] Accountant 收到 → 处理 → Bus("accounting.result", reply_to=msg_id)
    ↓
[5] Manager → Bus("audit.execute", reply_to=msg_id)
    ↓
[6] Auditor 收到 → 审核 → Bus("audit.result", reply_to=msg_id)
    ↓
[7] 如果不通过：
    Accountant 收到反馈 → 修正 → 循环 [4]-[6]，最多 3 轮
    ↓
[8] 通过 → Manager → 用户
```

### 核心组件

| 组件 | 职责 |
|------|------|
| `core/message_bus.py` | 消息总线（内存实现） |
| `core/protocol.py` | 消息协议定义 |
| `core/exceptions.py` | 异常类型定义 |
| `agents/base.py` | 异步 Agent 基类 |
| `agents/manager.py` | 异步 Manager |
| `agents/accountant.py` | 异步 Accountant |
| `agents/auditor.py` | 异步 Auditor |
| `main.py` | 启动和协调 |

---

## 7. 消息总线接口设计

```python
class MessageBus:
    """消息总线接口"""
    
    async def publish(message: Message) -> bool:
        """发布消息到指定 recipient"""
    
    async def send_with_reply(message: Message, timeout: float) -> Optional[Message]:
        """发送消息并等待回复（请求/响应模式）"""
    
    async def subscribe(agent_name: str, handler: Callable):
        """订阅消息"""
    
    async def receive(agent_name: str) -> Message:
        """接收消息（阻塞）"""
    
    async def reply(original: Message, content: str):
        """发送回复"""
```

---

## 8. 实现计划

### Phase 1: 核心基础设施

1. `core/protocol.py` - 消息协议定义
2. `core/exceptions.py` - 异常类型
3. `core/message_bus.py` - 消息总线实现
4. `core/agent.py` - 异步 Agent 基类

### Phase 2: Agent 重构

5. `agents/manager.py` - 异步化，通过 Bus 通信
6. `agents/accountant.py` - 异步化，订阅 Bus
7. `agents/auditor.py` - 异步化，订阅 Bus
8. `agents/base.py` - 简化为纯接口

### Phase 3: 集成测试

9. `main.py` - 启动 Bus，初始化 Agent
10. 端到端测试
11. 错误处理测试

### Phase 4: 文档同步

12. 更新 AGENTS.md
13. 更新架构文档

---

## 9. 设计原则

| 原则 | 实现 |
|------|------|
| **单一职责** | 每个模块只做一件事 |
| **开闭原则** | 加新 Agent 不改现有代码 |
| **依赖倒置** | Agent 依赖抽象（Bus 接口） |
| **松耦合** | Agent 只和 Bus 通信 |
| **高内聚** | 相关功能放一起 |

---

## 10. 未来扩展

### 迁移到 Redis

接口保持一致，只需替换实现：
```python
class RedisMessageBus(MessageBus):
    """Redis 实现的消息总线"""
```

### 添加新 Agent

1. 在 `agents/` 创建新 Agent 类，继承 `AsyncAgent`
2. 在 `main.py` 注册到 Bus
3. 无需修改其他 Agent

### 分布式部署

当需要跨机器运行时：
1. 部署 Redis
2. 替换 `InMemoryMessageBus` 为 `RedisMessageBus`
3. 其他代码不变
