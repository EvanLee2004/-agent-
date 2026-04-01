# 智能会计

<p align="center">
  <img src="assets/readme-hero.svg" alt="智能会计项目封面图" width="100%" />
</p>

基于 LLM 的智能会计助手，单 Agent 架构。  
当前版本已经从“收入/支出流水账助手”重构为“`skills + native function calling + deterministic services`”驱动的小企业会计系统雏形。

## 开发与架构来源

- **Claude Code**：用于项目开发过程中的代码重构、联调与工程化整理
- **Codex**：用于架构重构、函数调用接入、测试补全与文档整理
- **OpenCode**：作为项目目录组织、Skills 形态与 Agent 工程风格的重要参考

## 功能

- **记账**：把自然语言业务转成标准会计凭证并自动入账
- **查询**：查看历史凭证和分录
- **税务计算**：支持小规模纳税人增值税、小型微利企业企业所得税基础计算
- **审核**：支持基于规则的凭证审核
- **记忆**：支持长期记忆与每日记忆的显式写入与检索
- **规则问答**：支持基于项目规则和会计约束的说明性问答

## 架构

```text
用户
  ↓
AccountantAgent
  ↓
SkillPromptService（加载 .opencode/skills + 记忆 + 科目目录）
  ↓
ToolRuntime（原生 function calling）
  ↓
Tool Handlers
  ↓
Accounting / Tax / Audit / Memory Services
  ↓
Journal / Chart Repository + OpenClaw 风格记忆存储
```

项目参考 OpenCode 的 skills 目录形态，并结合 OpenClaw 风格记忆实现：  
`opencode.json` + `.opencode/skills/` + `MEMORY.md` + `memory/YYYY-MM-DD.md`

## 项目结构

```text
├── main.py                         # CLI 入口
├── bootstrap.py                    # 应用启动引导
├── agents/
│   ├── accountant_agent.py         # 智能会计主 Agent
│   └── factory.py                  # Agent 装配工厂
├── domain/                         # 领域模型
├── services/                       # 应用服务层
├── infrastructure/
│   ├── accounting_repository.py    # 凭证、分录、科目 Repository
│   ├── llm.py                      # Provider + LLM facade
│   ├── memory.py                   # OpenClaw 风格记忆存储
│   ├── memory_index.py             # SQLite FTS 记忆索引
│   └── skill_loader.py             # Skill 加载器
├── tools/                          # Tool runtime / registry / handlers
├── .opencode/
│   └── skills/                     # 原生 Skills 目录
├── skills/                         # 文档处理类 legacy helper scripts
├── MEMORY.md                       # 长期稳定记忆
├── memory/                         # 每日记忆（YYYY-MM-DD.md）
├── tests/                          # 自动化测试
├── opencode.json                   # OpenCode 项目配置
└── config.json                     # 模型配置
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
1. 选择 Provider（MiniMax / DeepSeek / OpenAI）
2. 选择 Model
3. 输入 API Key（保存到 `.env`）

也可以手动创建 `.env`：

```bash
LLM_API_KEY=your_key_here
```

### 3. 运行

```bash
python main.py
```

## 核心特性

### Native Function Calling

- 主流程不再依赖“模型输出 JSON，再由本地解析执行”的旧链路
- 第一轮强制调用至少一个工具，避免悄悄退回自由聊天
- 当前工具：
  - `record_voucher`
  - `query_vouchers`
  - `calculate_tax`
  - `audit_voucher`
  - `store_memory`
  - `search_memory`
  - `reply_with_rules`

### Skill 系统

- Skill 主入口是 `.opencode/skills/<name>/SKILL.md`
- Skills 现在只负责领域知识、工具使用规则和答复约束
- 业务类 legacy fallback skill 模板已经移除，避免旧文档和主流程冲突
- `skills/` 目录当前仅保留文档处理类 helper scripts

### 分录驱动账务模型

- 账务主存储为 `account_subject`、`journal_voucher`、`journal_line`
- 旧 `ledger` 兼容体系已经移除，当前只保留分录驱动主账
- 凭证必须借贷平衡

### 记忆系统

- 长期记忆写入根目录 `MEMORY.md`
- 短期/每日记忆写入 `memory/YYYY-MM-DD.md`
- Markdown 文件是源数据，SQLite FTS 只负责搜索
- 主流程通过原生 `store_memory` / `search_memory` 工具读写记忆

### 税务与审核

- 小规模纳税人增值税：按 1% 征收率基础计算
- 小型微利企业企业所得税：按 25% x 20% 有效税负基础计算
- 凭证审核覆盖借贷平衡、金额异常、摘要质量和重复凭证检查

## 测试

```bash
./.venv/bin/python -B -m unittest discover -s tests -v
```

当前已覆盖的主路径：
- 凭证记账与查询
- 税务计算
- 凭证审核
- 长期记忆写入与复用
- 规则问答
- `<think>` 清理
- 禁止无工具自由聊天

## 说明

- 本项目已经验证本地 stub 测试和真实 MiniMax 原生 function calling smoke test
- 文档处理类 skill 仍依赖 `skills/docx|pdf|pptx|xlsx/scripts/`

## License

MIT
