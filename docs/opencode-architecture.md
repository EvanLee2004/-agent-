# OpenCode 架构图

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenCode 核心                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Agent Service                          │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │    │
│  │  │  build  │ │  plan   │ │ general │ │ explore │ ...    │    │
│  │  │ (primary)│ │(primary)│ │(subagent)│ │(subagent)│       │    │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Skill Service                           │    │
│  │  get(name) / all() / available(agent) / dirs()         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Skill Discovery                         │    │
│  │  ~/.config/opencode/skills/<name>/SKILL.md             │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Agent 类型

| Agent | 模式 | 说明 |
|-------|------|------|
| build | primary | 主构建 agent |
| plan | primary | 计划 agent |
| general | subagent | 通用 subagent |
| explore | subagent | 代码探索 subagent |

## 3. 多 Agent 协作（agenthub skill）

```
主会话 (Coordinator)
    │
    ├─── git worktree 创建隔离环境
    │
    ├─── Subagent 1 ──▶ 独立执行任务 A
    ├─── Subagent 2 ──▶ 独立执行任务 B
    ├─── Subagent 3 ──▶ 独立执行任务 C
    │                  ...
    │
    ▼
结果评估 (LLM Judge / Metric)
    │
    ▼
合并最优结果
```

## 4. Skill 结构

```
skills/
├── SKILL.md                    # 必需：元数据 + 提示词
├── README.md                   # 可选：使用说明
├── scripts/                     # 可选：Python 工具脚本
│   ├── __init__.py
│   ├── execute.py
│   └── helper.py
├── references/                  # 可选：参考文档
└── assets/                     # 可选：示例数据
```

## 5. Agent 调用 Skill 流程

```
用户/Agent 识别需要 Skill
         │
         ▼
┌─────────────────────────┐
│ skill({ name: "xxx" })  │  ◀── Agent 调用 Skill Tool
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Permission 检查          │  ◀── 权限验证
│ allow / deny / ask      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 读取 SKILL.md 内容       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 扫描 scripts/ 目录      │
└───────────┬─────────────┘
            │
            ▼
     AI 执行任务
            │
            ▼
     （可选）调用 scripts/*.py
```

## 6. SKILL.md 格式

```yaml
---
name: "skill-name"              # 必需
description: "描述文字..."      # 必需
compatibility: "opencode"
---

# Skill 标题

## What I do
- 具体功能描述...

## When to use me
- 使用场景...

## Usage
- 使用方法...
```

## 7. Tier 分类系统

| Tier | SKILL.md | Scripts | LOC |
|------|----------|---------|-----|
| BASIC | ≥100行 | ≥1 | 100-300 |
| STANDARD | ≥200行 | 1-2 | 300-500 |
| POWERFUL | ≥300行 | 2-3 | 500-800 |

## 8. Agent 配置示例

```json
{
  "agent": {
    "build": {
      "mode": "primary",
      "model": "anthropic/claude-3",
      "permission": { "skill": { "*": "allow" } }
    },
    "explore": {
      "mode": "subagent",
      "model": "anthropic/claude-3",
      "permission": { "skill": { "*": "ask" } }
    }
  }
}
```
