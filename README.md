# 智能会计

基于 LLM 的智能会计助手，单 Agent 架构。

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

**参考 opencode 的设计**：长期记忆 + 模型选择系统。

## 项目结构

```
├── main.py                      # CLI 入口
├── agents/
│   └── accountant_agent.py      # 智能会计
├── infrastructure/
│   ├── llm.py                  # LLM 调用（从 config.json 读取配置）
│   ├── ledger.py               # 账目数据库
│   └── memory.py               # 长期记忆
├── providers/
│   ├── __init__.py            # Provider 定义（MiniMax/DeepSeek）
│   └── config.py             # 配置管理
├── skills/
│   ├── accounting/            # 记账 Skill
│   └── audit/                # 审核 Skill
├── memory/                     # 记忆存储
├── data/                       # 账目数据库
├── config.json                # 模型配置（provider/model）
├── .env                       # API 密钥（不上传 Git）
└── .env.example              # 环境变量模板
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置

首次运行会自动引导配置：
1. 选择 Provider（MiniMax/DeepSeek）
2. 选择 Model
3. 输入 API Key（保存在 `.env`）

或手动创建 `.env`：
```bash
LLM_API_KEY=your_key_here
```

### 3. 运行

```bash
python main.py
```

## 使用示例

```
当前: MiniMax - MiniMax-M2.7
==================================================
智能会计已启动 - 记账/查询（quit 退出）
==================================================

你: 报销差旅费500元，日期2024-01-15，说明客户拜访
助手: 记账成功 [ID:1]

你: 你好
助手: 你好！我是智能会计助手～
```

## 记账规则

- 金额超过 50000：标注"需审核"
- 金额低于 10 元：标注"金额过小"
- 自动记录交互到记忆

## 版本历史

- **v1.1** - 模型选择系统，支持 MiniMax/DeepSeek
- **v1.0** - 智能会计 1.0，单 Agent 架构

## License

MIT
