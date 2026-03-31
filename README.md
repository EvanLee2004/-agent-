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
cp .env.example .env
# 编辑 .env，填入你的 API Key
MINIMAX_API_KEY=your_key_here
```

### 3. 运行

```bash
python main.py
```

## 使用方式

```
你: 报销1000元差旅费
助手: ✅ 通过
      类型：支出
      金额：1000元
      说明：差旅费

你: 查看今天记账
助手: ID   时间                 类型   金额       说明          状态
      1    2026-03-30 15:30   支出   ¥1000.00   差旅费        ✅
      收入: ¥0.00  支出: ¥1000.00  结余: ¥-1000.00
```

## 清除测试数据

```bash
./clear_db.sh
```

## 项目结构

```
├── agents/          # AI Agent 代码
├── core/            # 基础设施（LLM、数据库、记忆）
├── memory/          # Agent 记忆
├── rules/          # 记账规则
└── data/           # 账目数据库
```

## 架构说明

### 核心模块

| 模块 | 职责 |
|------|------|
| `agents/base.py` | Agent 基类（公共工具方法） |
| `agents/manager.py` | 意图分类 + 协调流程 |
| `agents/accountant.py` | 记账执行 |
| `agents/auditor.py` | 审核执行 |

### 设计理念

**本质是提示词工程**：每个 Agent 的行为由 `SYSTEM_PROMPT` 决定，通过 `ask_llm()` 方法与 LLM 自然语言交互。

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
