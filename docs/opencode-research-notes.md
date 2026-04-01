# OpenCode 源码研究笔记

深入研究 opencode 源码后的架构发现。

---

## 1. OpenCode 有没有 Core 层？

**结论：没有 "core" 层概念**，而是模块化服务结构：

```
packages/opencode/src/
├── provider/     # LLM provider 管理（中心化）
├── agent/        # Agent 定义
├── session/      # 聊天会话 + LLM 调用
├── skill/        # Skill 发现/加载（只读元数据）
├── plugin/       # 插件系统
├── config/       # 配置管理
├── auth/         # 认证
├── tool/         # 工具定义
└── ...其他模块
```

**共享基础设施包括**：
- **Effect Framework**: 使用 `effect` 库做依赖注入和服务层
- **Provider Service**: 中心化 LLM Provider 管理
- **LLM Service**: 中心化 LLM 调用处理

---

## 2. OpenCode 如何处理 LLM 调用？

**高度中心化**：

主要 LLM 入口是 `LLM.stream()` 在 `session/llm.ts`：

```typescript
// session/llm.ts
export async function stream(input: StreamRequest) {
  const language = await Provider.getLanguage(input.model)  // 从 Provider 获取模型
  return streamText({  // 使用 Vercel AI SDK
    model: wrapLanguageModel({ model: language, ... }),
    messages,
    tools,
  })
}
```

**Provider Service** 在 `provider/provider.ts`：

```typescript
// Provider Service
const BUNDLED_PROVIDERS = {
  "@ai-sdk/amazon-bedrock": createAmazonBedrock,
  "@ai-sdk/anthropic": createAnthropic,
  "@ai-sdk/openai": createOpenAI,
  "@openrouter/ai-sdk-provider": createOpenRouter,
  // ... 更多
}
```

---

## 3. 有多少个 LLM 调用入口？

**一个主要入口**：`LLM.stream()` 在 `session/llm.ts`

次级入口（构建在上面）：
- `Agent.generate()` - 使用 `generateObject()` 做 Agent 生成
- `session/summary.ts`
- `session/compaction.ts`

所有 LLM 交互都通过 `Provider` 服务获取 `LanguageModelV3`。

---

## 4. LLM Client 定义在哪里？

**主要位置**：`packages/opencode/src/provider/provider.ts`

```typescript
async function resolveSDK(model: Model, s: State) {
  const bundledFn = BUNDLED_PROVIDERS[model.api.npm]
  if (bundledFn) {
    return bundledFn({ name: model.providerID, ...options })
  }
  // 动态加载其他 provider...
}
```

**底层 LLM SDK**：Vercel `ai` SDK（`streamText`, `generateObject`）

---

## 5. Skill 在 OpenCode 中如何工作？

**重要发现**：OpenCode 的 Skill **不是独立的 LLM 调用点**！

```
Skill 工作方式：
1. Skill 内容（SKILL.md）被 Skill.Service 加载
2. SYSTEM_PROMPT 从 SKILL.md 提取
3. SYSTEM_PROMPT 被注入到 LLM 调用中
4. LLM 在 session 层统一处理
```

**Skill 的角色**：
- 提供提示词模板（SKILL.md）
- 可能提供 scripts/ 工具脚本
- **不直接调用 LLM**（LLM 调用在 session 层统一）

---

## 6. 中心化 vs 分布式的区别

| 方面 | OpenCode | 我们的项目 |
|------|----------|-----------|
| **Core 概念** | 无 - 模块化服务 | 有 - core/ 基础设施 |
| **LLM 调用** | **高度中心化** via Provider.Service + LLM.stream() | 去中心化，每个 Skill 自己调 |
| **LLM SDK** | Vercel `ai` SDK | 直接 OpenAI SDK |
| **Skill 角色** | 只提供提示词模板 | 独立进程 + subprocess 调用 |
| **Provider 抽象** | 多个内置 Provider | .env 配置 |

---

## 7. 架构对比

### OpenCode 架构

```
┌─────────────────────────────────────┐
│          Provider.Service            │  ← 中心化 LLM 管理
│          (provider.ts)               │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│           LLM.stream()                │  ← 唯一 LLM 入口
│          (session/llm.ts)           │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│            Agent 生成                  │
│         + Tool 执行                   │
└─────────────────────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         Skill.Service                 │  ← 只加载 SKILL.md
│          (skill/)                    │     提供 SYSTEM_PROMPT
└─────────────────────────────────────┘
```

### 我们的项目架构

```
┌─────────────────────────────────────┐
│         Agent 层                      │
│   Manager / Accountant / Auditor      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│        SkillLoader                    │  ← Skill 加载器
│        (core/skill_loader.py)         │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     Skill 脚本（独立进程）            │  ← 每个 Skill 自己调 LLM
│   coordination / accounting / audit   │
└─────────────────────────────────────┘
               │
┌──────────────▼──────────────────────┐
│        Core 层基础设施                │
│    llm / ledger / memory / rules      │
└─────────────────────────────────────┘
```

---

## 8. 关键区别

| 方面 | OpenCode | 我们的项目 |
|------|----------|-----------|
| **LLM 调用** | 中心化，单一入口 | 去中心化，每个 Skill 独立调 |
| **Skill 定位** | 提示词提供者 | 独立计算单元 |
| **Agent 定位** | 内置（build/explore） | 自定义（Manager/Accountant/Auditor） |
| **代码复用** | Effect 服务共享 | core/ 模块共享 |

---

## 9. OpenCode 的优势

1. **Effect 框架**：依赖注入，服务可测试
2. **中心化 LLM**：统一管理、日志、插件钩子
3. **动态 Provider 加载**：支持多种 LLM Provider
4. **插件钩子**：`chat.params`、`chat.headers` 等

---

## 10. 我们可以借鉴的地方

| 借鉴 | 说明 |
|------|------|
| **LLM 调用中心化** | 考虑让 Skill 不直接调 LLM，而是返回数据，Agent 统一调 |
| **Provider 抽象** | 更灵活的 LLM Provider 切换 |
| **插件钩子** | 未来可加审计、日志钩子 |

---

## 11. OpenCode 上下文窗口管理（Compaction）

**重要发现**：OpenCode 实现了自动上下文压缩机制，支持长会话。

### 11.1 自动压缩触发机制

位置：`internal/tui/tui.go`

```go
// 当响应完成且 token 超过上下文窗口 95% 时触发
if payload.Done && payload.Type == agent.AgentEventTypeResponse {
    model := a.app.CoderAgent.Model()
    contextWindow := model.ContextWindow  // e.g., 200000 for Claude 200k
    tokens := a.selectedSession.CompletionTokens + a.selectedSession.PromptTokens
    if (tokens >= int64(float64(contextWindow)*0.95)) && config.Get().AutoCompact {
        return a, util.CmdHandler(startCompactSessionMsg{})
    }
}
```

**关键点**：
- 阈值：上下文窗口的 **95%**
- 默认：**启用**（`autoCompact: true`）
- 可手动触发：`compact` 命令

### 11.2 Session 结构（token 追踪）

位置：`internal/session/session.go`

```go
type Session struct {
    ID               string
    ParentSessionID  string
    Title            string
    MessageCount     int64
    PromptTokens     int64           // 累计输入 token
    CompletionTokens int64           // 累计输出 token
    SummaryMessageID string          // 指向摘要消息
    Cost             float64
    CreatedAt        int64
    UpdatedAt        int64
}
```

### 11.3 Summarization 流程

位置：`internal/llm/agent/agent.go` - `Summarize` 方法

1. **获取所有消息**
2. **创建摘要 prompt**：
   ```
   "Provide a detailed but concise summary of our conversation above.
    Focus on information that would be helpful for continuing the conversation,
    including what we did, what we're doing, which files we're working on,
    and what we're going to do next."
   ```
3. **发送给 summarizer provider**（可以使用与主 agent 不同的模型）
4. **在 session 中创建摘要消息**
5. **更新 session**：`SummaryMessageID = msg.ID`

```go
oldSession.SummaryMessageID = msg.ID
oldSession.CompletionTokens = response.Usage.OutputTokens
oldSession.PromptTokens = 0  // 重置计数器
```

### 11.4 Token 计算与追踪

位置：`internal/llm/provider/provider.go`

```go
type TokenUsage struct {
    InputTokens         int64
    OutputTokens        int64
    CacheCreationTokens int64  // 缓存上下文 token
    CacheReadTokens     int64  // 从缓存读取的 token
}
```

**Model 结构**（`internal/llm/models/models.go`）：
```go
type Model struct {
    ContextWindow       int64  // e.g., 200000 for Claude 200k
    DefaultMaxTokens    int64
    // ...
}
```

### 11.5 对话历史管理

**消息过滤**（在 `agent.go` `processGeneration`）：

当 session 有摘要时，只使用摘要之后的消息：

```go
if session.SummaryMessageID != "" {
    summaryMsgIndex := -1
    for i, msg := range msgs {
        if msg.ID == session.SummaryMessageID {
            summaryMsgIndex = i
            break
        }
    }
    if summaryMsgIndex != -1 {
        msgs = msgs[summaryMsgIndex:]  // 从摘要开始
        msgs[0].Role = message.User    // 让摘要成为 user 消息
    }
}
```

### 11.6 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         TUI (tui.go)                         │
│  监控每次响应后的 token 使用量                                │
│  当超过上下文窗口 95% 时触发 auto-compact                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Service (agent.go)                  │
│  - Run(): 主 agent 循环                                      │
│  - Summarize(): 创建摘要                                     │
│  - TrackUsage(): 更新 token 计数                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Session Service (session/session.go)            │
│  - 存储 session 元数据                                       │
│  - 追踪 PromptTokens, CompletionTokens                       │
│  - 存储 SummaryMessageID（摘要锚点）                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│             Message Service (message/message.go)              │
│  - 存储所有对话消息                                          │
│  - 提供消息历史检索                                          │
└─────────────────────────────────────────────────────────────┘
```

### 11.7 核心设计洞察

1. **Token 累积**：Token 在整个 session 生命周期内累积
2. **95% 阈值**：当总 token 超过上下文窗口 95% 时触发摘要
3. **摘要作为检查点**：摘要消息成为 pivot point；其之前的 history 被"压缩"
4. **分离的 summarizer**：可以使用不同的模型做摘要
5. **持久化存储**：所有消息存在 SQLite，session 追踪元数据和摘要指针

### 11.8 相关文件

| 文件 | 用途 |
|------|------|
| `internal/tui/tui.go` | TUI 事件循环，95% 触发 auto-compact |
| `internal/llm/agent/agent.go` | `Summarize()` 方法，token 追踪 |
| `internal/session/session.go` | Session 结构体，含 token 计数 |
| `internal/message/message.go` | 消息存储和检索 |
| `internal/llm/models/models.go` | 每个模型的 `ContextWindow` |
| `internal/llm/provider/provider.go` | `TokenUsage` 结构体 |
| `internal/config/config.go` | `AutoCompact` 配置项 |

---

## 附录：相关文件路径

| 功能 | 路径 |
|------|------|
| Provider Service | `packages/opencode/src/provider/provider.ts` |
| LLM Service | `packages/opencode/src/session/llm.ts` |
| Agent | `packages/opencode/src/agent/agent.ts` |
| Skill Service | `packages/opencode/src/skill/` |
| Plugin Hooks | `packages/opencode/src/plugin/` |
| Context Compaction | `internal/tui/tui.go` |
| Summarization | `internal/llm/agent/agent.go` |
| Session | `internal/session/session.go` |
| Message | `internal/message/message.go` |
