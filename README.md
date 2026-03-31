# 智能财务部门

多 Agent 协作模拟会计部门工作流程的 CLI 应用。

## 角色

| 角色 | 职责 |
|------|------|
| **Manager** | 理解意图、协调流程、汇总返回 |
| **Accountant** | 记账、讨论修改 |
| **Auditor** | 审核、标注问题 |

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
你: 报销1000元差旅费
助手: ✅ [ID:1] 支出 1000.0元 - 差旅费报销

你: 查看今天记账
助手: ID   时间                 类型   金额       说明          状态
      1    2026-04-01 15:30   支出   ¥1000.00   差旅费        ✅
      收入: ¥0.00  支出: ¥1000.00  结余: ¥-1000.00
```

## 清除测试数据

```bash
./clear_db.sh
```

## 项目结构

```
├── agents/          # AI Agent 代码（角色）
├── core/            # 基础设施（LLM、数据库、记忆）
├── skills/          # Skill 能力包
│   ├── coordination/  # 协调 Skill
│   ├── accounting/    # 记账 Skill
│   └── audit/        # 审计 Skill
├── memory/          # Agent 记忆
├── rules/          # 记账规则
└── data/           # 账目数据库
```

## 架构说明

### Agent vs Skill

| 概念 | 说明 |
|------|------|
| Agent（角色） | 在 `agents/`，负责业务逻辑（写库、流程控制、调用 LLM） |
| Skill（能力包） | 在 `skills/`，被 Agent 调用，负责纯计算（返回 prompt 数据） |

### 核心模块

| 模块 | 职责 |
|------|------|
| `agents/base.py` | Agent 基类（公共工具方法） |
| `agents/manager.py` | 协调流程 |
| `agents/accountant.py` | 记账执行 |
| `agents/auditor.py` | 审核执行 |
| `core/skill_loader.py` | Skill 加载器 |

### 设计理念

**本质是提示词工程**：每个 Agent 的行为由 `SYSTEM_PROMPT` 决定。

**Skill 独立化**：Skill 脚本不依赖 core/，只用标准库 + openai SDK，换模型只需改 `.env`。

### 工作流程

```
用户输入 → Manager 意图分类 → Accountant 记账 → Auditor 审核(最多3轮)
                                                        ↓
                                                   通过 → 写入 ledger.db
                                                        ↓
                                                   Manager 汇总 → 用户
```

### 数据流

```
用户 → Manager.process() → _classify_intent() → 路由
                                              ↓
                          ┌───────────────────┼───────────────────┐
                          ↓                   ↓                   ↓
              _handle_accounting()   _handle_review()   _handle_transfer()
                          ↓                   ↓
                    Accountant ←→ Auditor   查询 ledger.db
                          ↓
                    写入 ledger.db
                          ↓
                    返回结果
```

### Skill 系统

```
Skill = SKILL.md + scripts/*.py

skills/coordination/
├── SKILL.md           # SYSTEM_PROMPT
└── scripts/
    └── intent.py     # 意图分类

skills/accounting/
├── SKILL.md
└── scripts/
    └── execute.py    # 记账执行

skills/audit/
├── SKILL.md
└── scripts/
    └── execute.py    # 审核执行
```

换模型只需修改 `.env`：

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4
```

## 引用

本项目在设计与实现过程中参考了以下开源项目：

- **opencode** - 一个 AI 编程助手框架，提供了 Skill 系统的设计思路  
  <https://github.com/anomalyco/opencode>
