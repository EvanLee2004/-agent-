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

## 附录：相关文件路径

| 功能 | 路径 |
|------|------|
| Provider Service | `packages/opencode/src/provider/provider.ts` |
| LLM Service | `packages/opencode/src/session/llm.ts` |
| Agent | `packages/opencode/src/agent/agent.ts` |
| Skill Service | `packages/opencode/src/skill/` |
| Plugin Hooks | `packages/opencode/src/plugin/` |
