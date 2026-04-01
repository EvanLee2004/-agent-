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
      LLM 判断意图（结构化 JSON 输出）
           ↓
      Skill 系统（可选）/ 直接执行
           ↓
      Repository 模式数据库
           ↓
      长期记忆学习
```

**参考 opencode 的设计**：长期记忆 + 模型选择系统 + Skill 系统。

## 项目结构

```
├── main.py                      # CLI 入口
├── agents/
│   └── accountant_agent.py      # 智能会计（AccountantAgent 类）
├── infrastructure/
│   ├── llm.py                  # LLM 调用（重试+异常处理+超时）
│   ├── ledger.py               # 数据库接口（向后兼容）
│   ├── ledger_repository.py    # Repository 模式（SQLite 实现）
│   ├── memory.py               # 长期记忆系统
│   └── skill_loader.py        # Skill 加载器
├── providers/
│   ├── __init__.py            # Provider 定义（MiniMax/DeepSeek）
│   └── config.py             # 配置管理（含验证层）
├── skills/
│   ├── docx/                   # Word 文档处理（Anthropic）
│   ├── pdf/                     # PDF 文档处理（Anthropic）
│   ├── pptx/                    # PPT 演示文稿处理（Anthropic）
│   ├── xlsx/                    # Excel 电子表格处理（Anthropic）
│   ├── rules/                   # 中国会计准则
│   ├── tax/                    # 中国税务（待开源替代）
│   ├── audit/                   # 账目审核
│   ├── accounting/              # 智能记账
│   └── accounting/reference/    # 参考资料（Beancount, IFRS）
├── memory/                     # 记忆存储（JSON）
├── data/                       # 账目数据库（SQLite）
└── config.json                # 模型配置
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

## 核心特性

### LLM 调用稳定性
- 自动重试（最多 3 次）
- 指数退避策略
- 超时控制（30 秒）
- 网络异常降级处理

### 结构化意图识别
- JSON 格式输出
- 自动降级到正则匹配（兼容旧格式）
- 意图类型：`accounting` / `query` / `chat`

### 依赖注入架构
- `AccountantAgent` 类支持自定义 LLM 客户端
- 便于单元测试和模型切换

### Skill 系统
- 8 个可加载技能：docx, pdf, pptx, xlsx, rules, tax, audit, accounting
- 通过 subprocess 隔离执行
- 支持 JSON 输出格式

#### 技能分类

| 类别 | 技能 | 说明 |
|------|------|------|
| 文档处理 | docx, pdf, pptx, xlsx | Anthropic 官方 |
| 会计专业 | rules, tax, audit, accounting | 中国会计准则/税务/审核/记账 |

### Repository 模式
- 抽象数据库接口
- 支持未来迁移到 PostgreSQL/MySQL
- 单例模式全局访问

### 配置验证
- 启动时验证 provider/model/base_url
- 明确的错误提示

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

- **v2.0** - 架构优化：LLM 重试机制、结构化输出、依赖注入、Repository 模式、配置验证
- **v1.1** - 模型选择系统，支持 MiniMax/DeepSeek
- **v1.0** - 智能会计 1.0，单 Agent 架构

## License

MIT
