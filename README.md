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

```
用户 → Manager → Accountant 记账 → Auditor 审核(3轮)
                               ↓
                          通过 → 写入 ledger.db
                               ↓
                          Manager 汇总 → 用户
```
