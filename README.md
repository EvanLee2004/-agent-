# 智能财务部门

<p align="center">
  <img src="assets/readme-hero.svg" alt="智能财务部门项目封面图" width="100%" />
</p>

面向小企业财务场景的智能财务多 Agent 部门产品。当前阶段已经把底层会话运行时切到 **DeerFlow public client**，并把财务部门角色目录、DeerFlow 角色资产和财务工具边界收口到正式工程结构中。  
这一版的目标不是继续堆单点技巧，而是把 **DeerFlow 底座 + 财务部门业务壳 + 角色注册** 接稳，再逐步打开真实多角色协作。

## 开发与架构来源

- **Claude Code**
- **Codex**
- **DeerFlow**

## 当前能力

- **凭证记账**：把自然语言业务转换为标准会计凭证并入账
- **凭证查询**：按日期和状态检索历史凭证
- **税务测算**：支持小规模纳税人增值税、小型微利企业企业所得税基础测算
- **凭证审核**：支持金额异常、摘要质量、重复入账等规则审核
- **长期记忆与每日记忆**：支持显式写入、检索和召回
- **规则问答**：支持基于项目规则和会计约束的说明性问答

## 当前阶段

当前版本已经完成：

- DeerFlow 公开嵌入客户端接入
- 财务工具注册到 DeerFlow runtime
- DeerFlow skill 资产落地
- 财务部门五角色目录落地
- DeerFlow 自定义角色资产自动生成
- CLI 主链路切换到 DeerFlow 底层

当前版本**尚未**完成：

- 基于公开 client 的角色间编排协作
- 正式税务申报
- API/Web 对外接口

## 当前架构

```text
用户
  ↓
CLI / 未来 API
  ↓
ConversationRouter
  ↓
ConversationService
  ↓
DeerFlowAgentRuntimeRepository
  ↓
DeerFlowClient（public embedded client）
  ↓
财务部门角色资产 + DeerFlow skills + 财务工具
  ↓
Feature Routers
  ↓
Feature Services
  ↓
SQLite / Markdown Memory
```

关键原则：

- DeerFlow 只负责通用 agent runtime
- 财务业务规则仍由本项目自己维护
- 当前只依赖 DeerFlow 的**公开 client**，不依赖它的内部模块

## 项目结构

```text
├── main.py
├── app/                             # 启动入口与依赖装配
├── conversation/                    # 会话边界与 DeerFlow 适配层
├── department/                      # 财务部门角色目录、角色资产与工具上下文
├── accounting/                      # 记账与凭证查询
├── audit/                           # 审核规则
├── tax/                             # 税务测算
├── memory/                          # 长期/每日记忆与搜索索引
├── rules/                           # 规则问答
├── configuration/                   # 配置读取与校验
├── .agent_assets/
│   ├── deerflow_skills/             # DeerFlow 当前阶段使用的 skill 资产
│   └── skills/                      # 本项目长期维护的领域 prompt 资产
├── MEMORY.md                        # 长期记忆
├── memory/                          # 每日记忆（YYYY-MM-DD.md）
├── tests/
└── config.json
```

## 配置

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置模型

准备 `.env`：

```bash
LLM_API_KEY=your_key_here
```

准备 `config.json`：

```json
{
  "provider": "minimax",
  "model": "MiniMax-M2.7",
  "base_url": "https://api.minimaxi.com/v1"
}
```

### 3. 运行

```bash
python main.py
```

运行时会自动在 `.agent_assets/runtime/deerflow/` 下生成 DeerFlow 配置与状态目录；该目录为本地运行资产，已被忽略，不应提交到远端。

## DeerFlow 接入方式

本项目当前通过 `DeerFlowClient` 接入 DeerFlow：

- 使用 DeerFlow 的公开嵌入客户端
- 使用 DeerFlow 的配置驱动工具加载
- 使用本项目自己的财务 tools 和业务 service

当前已接入的财务工具：

- `record_voucher`
- `query_vouchers`
- `calculate_tax`
- `audit_voucher`
- `store_memory`
- `search_memory`
- `reply_with_rules`

当前 DeerFlow skill 资产位于：

- `.agent_assets/deerflow_skills/public/finance-core/SKILL.md`
- `.agent_assets/deerflow_skills/public/coordinator/SKILL.md`
- `.agent_assets/deerflow_skills/public/bookkeeping/SKILL.md`
- `.agent_assets/deerflow_skills/public/policy-research/SKILL.md`
- `.agent_assets/deerflow_skills/public/tax/SKILL.md`
- `.agent_assets/deerflow_skills/public/audit/SKILL.md`

## 记忆系统

- 长期记忆写入根目录 `MEMORY.md`
- 每日记忆写入 `memory/YYYY-MM-DD.md`
- Markdown 文件是源数据
- SQLite FTS 索引只负责搜索，不是主存储

## 测试

```bash
./.venv/bin/python -B -m unittest discover -s tests -v
```

当前测试覆盖：

- DeerFlow 运行时资产生成
- 财务部门角色目录与角色资产生成
- DeerFlow public client 读取 skill
- DeerFlow 工具注册
- 记账与查账
- 税务测算
- 凭证审核
- 记忆写入与召回
- 会话边界与线程透传

## 当前里程碑结论

- 已完成 DeerFlow 底层接入
- 已完成财务 tools 对接
- 已完成财务部门角色注册与 DeerFlow 角色资产生成
- 已保留会计业务核心在本项目内
- 下一步是基于公开 client 打开角色协作，而不是继续扩 runtime 杂项

## License

MIT
