# 智能会计

基于 LLM 的智能会计助手，单 Agent 架构，处理记账、查询等财务任务。

## 功能

- **记账**：记录收入、支出，自动异常检测
- **查询**：查看历史账目
- **记忆**：从交互中学习，积累经验
- **智能闲聊**：LLM 驱动的自然对话

## 架构

```
用户 → 智能会计（单 Agent）
           ↓
      LLM 判断意图
           ↓
     执行/回复
```

**参考 opencode 的记忆设计**：长期记忆存储在 JSON 文件中。

## 项目结构

```
├── main.py                      # CLI 入口
├── agents/
│   └── accountant_agent.py      # 智能会计
├── infrastructure/
│   ├── llm.py                  # LLM 调用
│   ├── ledger.py               # 账目数据库
│   ├── skill_loader.py         # Skill 加载器
│   └── memory.py               # 长期记忆
├── skills/
│   ├── accounting/             # 记账 Skill
│   └── audit/                  # 审核 Skill
├── memory/                     # 记忆存储
├── data/                       # 账目数据库
└── .env                       # 环境配置
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 编辑 .env
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.minimax.chat/v1
LLM_MODEL=MiniMax-M2.7
```

### 3. 运行

```bash
python main.py
```

## 使用示例

```
智能会计已启动 - 记账/查询（quit 退出）

你: 报销差旅费500元，日期2024-01-15，说明客户拜访
助手: 记账成功 [ID:1]

你: 查看账目
助手: [1] ⏳ 2024-01-15 | 支出 500.0元 | 客户拜访

你: 你是谁
助手: 我是智能会计助手，负责帮你处理记账和查询～
```

## 记账规则

- 金额超过 50000：标注"需审核"
- 金额低于 10 元：标注"金额过小"
- 自动记录每次交互到记忆

## 版本历史

- **v1.0** - 智能会计 1.0，单 Agent 架构，集成长期记忆

## License

MIT
