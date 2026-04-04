# 智能财务部门

<p align="center">
  <img src="assets/readme-hero.svg" alt="智能财务部门项目封面图" width="100%" />
</p>

面向小企业财务场景的智能财务多 Agent 部门产品。当前阶段已经把底层会话运行时切到 **DeerFlow public client**，并把财务部门角色目录、共享工作台、DeerFlow 角色资产和财务工具边界收口到正式工程结构中。  
这一版的目标不是继续堆单点技巧，而是把 **DeerFlow 底座 + 财务部门业务壳 + 角色协作协议** 接稳，再逐步打开真实多角色协作，并让底层配置结构尽量和 DeerFlow 官方 `config.yaml` 同构。

## 开发与架构来源

- **Claude Code**
- **Codex**
- **DeerFlow**

## 当前能力

- **凭证记账**：把自然语言业务转换为标准会计凭证并入账
- **凭证查询**：按日期和状态检索历史凭证
- **资金事实管理**：记录和查询收款、付款、报销支付等出纳事实
- **税务测算**：支持小规模纳税人增值税、小型微利企业企业所得税基础测算
- **凭证审核**：支持金额异常、摘要质量、重复入账等规则审核
- **DeerFlow 原生记忆**：由 DeerFlow runtime 自动抽取事实并注入后续对话
- **规则问答**：支持基于项目规则和会计约束的说明性问答
- **角色思考可视化**：展示每个财务角色的协作摘要，而不是暴露原始推理全文
- **多模型底层配置**：配置结构已经升级为 DeerFlow 风格 `default_model + models[]`

## 当前阶段

当前版本已经完成：

- DeerFlow 公开嵌入客户端接入
- DeerFlow runtime 基础工具组接入
- DeerFlow 风格多模型配置落地
- DeerFlow client 运行时开关配置化
- 财务工具注册到 DeerFlow runtime
- DeerFlow skill 资产落地
- 财务部门六角色目录落地
- DeerFlow 自定义角色资产自动生成
- CLI 主链路切换到 DeerFlow 底层
- 共享工作台与角色协作 trace 落地

当前版本**尚未**完成：

- 完全切到 DeerFlow 原生 subagent 编排
- 基于真实业务状态的复杂多角色协同策略
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
FinanceDepartmentService
  ↓
共享工作台 + 角色协作服务
  ↓
DeerFlowDepartmentRoleRuntimeRepository
  ↓
DeerFlowClient（public embedded client）
  ↓
财务部门角色资产 + DeerFlow skills + DeerFlow 基础工具 + 财务工具 / 协作工具
  ↓
Feature Routers
  ↓
Feature Services
  ↓
SQLite 业务仓储 + DeerFlow Native Memory / Checkpointer
```

关键原则：

- DeerFlow 只负责通用 agent runtime
- 财务业务规则仍由本项目自己维护
- 当前只依赖 DeerFlow 的**公开 client**，不依赖它的内部模块

## 项目结构

```text
├── main.py
├── app/                             # 启动入口与依赖装配
├── conversation/                    # 会话边界与用户可见响应收口
├── runtime/                         # 第三方运行时适配层（当前为 DeerFlow）
├── department/                      # 财务部门主域
│   ├── collaboration/               # 角色协作协议与协作工具
│   ├── roles/                       # 六个财务角色的独立定义
│   └── workbench/                   # 共享工作台与角色轨迹
├── accounting/                      # 记账与凭证查询
├── cashier/                         # 出纳事实与资金收付
├── audit/                           # 审核规则
├── tax/                             # 税务测算
├── rules/                           # 规则问答
├── configuration/                   # 配置读取与校验
├── .agent_assets/
│   ├── deerflow_skills/             # DeerFlow 当前阶段使用的 skill 资产
│   └── skills/                      # 本项目长期维护的领域 prompt 资产
├── MEMORY.md                        # 长期记忆
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

### 2. 配置模型与 DeerFlow runtime

准备 `.env`：

```bash
MINIMAX_API_KEY=your_key_here
# 可选：
# DEEPSEEK_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
```

准备 `config.json`：

```json
{
  "default_model": "minimax-main",
  "models": [
    {
      "name": "minimax-main",
      "provider": "minimax",
      "model": "MiniMax-M2.7",
      "base_url": "https://api.minimaxi.com/v1",
      "api_key_env": "MINIMAX_API_KEY"
    },
    {
      "name": "deepseek-research",
      "provider": "deepseek",
      "model": "deepseek-reasoner",
      "base_url": "https://api.deepseek.com/v1",
      "api_key_env": "DEEPSEEK_API_KEY"
    }
  ],
  "deerflow_runtime": {
    "client": {
      "thinking_enabled": true,
      "subagent_enabled": false,
      "plan_mode": false
    },
    "tool_search": {
      "enabled": false
    },
    "sandbox": {
      "use": "deerflow.sandbox.local:LocalSandboxProvider",
      "allow_host_bash": false,
      "bash_output_max_chars": 20000,
      "read_file_output_max_chars": 50000
    }
  }
}
```

如果你暂时只用一个模型，也建议仍然保持这个结构。这样后续切模型或按角色分配模型时，不需要再迁移配置格式。

### 3. 运行

```bash
python main.py
```

运行时会自动在 `.runtime/deerflow/` 下生成 DeerFlow 配置与状态目录；该目录为本地运行资产，已被忽略，不应提交到远端。

## DeerFlow 接入方式

本项目当前通过 `DeerFlowClient` 接入 DeerFlow：

- 使用 DeerFlow 的公开嵌入客户端
- 使用 DeerFlow 的配置驱动工具加载
- 使用本项目自己的财务 tools 和业务 service

当前已接入的财务工具：

- `collaborate_with_department_role`
- `record_voucher`
- `query_vouchers`
- `record_cash_transaction`
- `query_cash_transactions`
- `calculate_tax`
- `audit_voucher`
- `reply_with_rules`

当前同时开放的 DeerFlow 基础工具组包括：

- `web_search`
- `web_fetch`
- `image_search`
- `ls`
- `read_file`
- `write_file`
- `str_replace`
- `bash`

当前 DeerFlow skill 资产位于：

- `.agent_assets/deerflow_skills/public/finance-core/SKILL.md`
- `.agent_assets/deerflow_skills/public/coordinator/SKILL.md`
- `.agent_assets/deerflow_skills/public/cashier/SKILL.md`
- `.agent_assets/deerflow_skills/public/bookkeeping/SKILL.md`
- `.agent_assets/deerflow_skills/public/policy-research/SKILL.md`
- `.agent_assets/deerflow_skills/public/tax/SKILL.md`
- `.agent_assets/deerflow_skills/public/audit/SKILL.md`

## 记忆系统

- 运行时对话记忆由 DeerFlow 原生 memory 负责
- 事实会写入 `.runtime/deerflow/home/agents/<agent_name>/memory.json`
- 记忆注入由 DeerFlow system prompt 自动完成，不再通过 `store_memory` / `search_memory` 工具显式驱动
- 根目录 `MEMORY.md` 是项目工程长期记忆，不是产品运行时用户记忆

## 测试

```bash
./.venv/bin/python -B -m unittest discover -s tests -v
```

当前测试覆盖：

- DeerFlow 运行时资产生成
- 多模型配置加载与持久化
- 财务部门角色目录与角色资产生成
- DeerFlow public client 读取 skill
- DeerFlow 工具注册
- DeerFlow client 运行时开关透传
- 角色协作服务与共享工作台
- 记账与查账
- 资金收付记录与查询
- 税务测算
- 凭证审核
- DeerFlow 原生记忆配置注入
- 会话边界与线程透传

## 当前里程碑结论

- 已完成 DeerFlow 底层接入与多模型配置收口
- 已完成财务 tools 对接
- 已完成财务部门角色注册、角色资产生成与共享工作台
- 已保留会计业务核心在本项目内
- 下一步是继续细化真实财务协同策略，并评估何时把角色协作进一步切向 DeerFlow 原生 subagent

## License

MIT
