# Agent 开发指南

本文档面向在本仓库中工作的 AI Agent。

## 当前阶段

当前项目已经不再继续沿着“单 Agent + 自研 tool loop”演进。  
这一阶段的真实目标是：

- 用 **DeerFlow public client** 作为底层 agent runtime
- 用本项目自己的财务业务代码承载记账、查账、审核、税务测算和记忆
- 把“智能财务部门”的角色目录、角色资产和工具边界收口到正式结构
- 只依赖 DeerFlow 的公开嵌入入口，不把业务代码绑到内部实现

## 最重要的规则

1. **生成的代码必须带详细中文注释**
   - 注释解释为什么这样设计、边界在哪里、为什么不能简化
   - 不写“给变量赋值”这种低价值注释

2. **严格分层**
   - `router -> service -> repository -> model`
   - 禁止跨层直接调用
   - 具体实现和第三方接入只允许在 `app/` 或明确的适配层装配

3. **按功能模块组织**
   - 不按 `services/`, `infrastructure/`, `domain/` 这种横切目录继续扩展
   - 一个文件一个类为默认原则
   - 禁止新增 `utils.py` / `helpers.py`

4. **DeerFlow 只走公开入口**
   - 允许依赖 `deerflow.client.DeerFlowClient`
   - 不允许 deep import DeerFlow 内部模块作为主工程依赖
   - 若确需参考 DeerFlow 原码，只能作为受控借鉴，不得让业务代码直接绑定内部实现

5. **业务逻辑优先**
   - 通用 orchestration 交给 DeerFlow
   - 财务业务规则必须留在本项目：
     - 凭证
     - 分录
     - 审核
     - 税前准备
     - 记忆策略

6. **错误处理必须明确**
   - 禁止裸 `except`
   - 禁止向最终用户直接暴露第三方 runtime 细节
   - 业务错误使用模块内异常类

7. **每次改动都要可验证**
   - 先读代码再改
   - 改完必须补测试或更新测试
   - 完成后必须重跑测试

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
DepartmentWorkbenchService + DepartmentCollaborationService
  ↓
runtime/deerflow/DeerFlowDepartmentRoleRuntimeRepository
  ↓
DeerFlowClient（public embedded client）
  ↓
财务部门角色资产 + DeerFlow skills + 财务工具
  ↓
Feature Routers
  ↓
Feature Services
  ↓
Repositories + SQLite / Markdown Memory
```

## 当前目录结构

```text
├── main.py
├── app/
├── conversation/
├── runtime/
├── department/
│   └── roles/
├── cashier/
├── accounting/
├── audit/
├── tax/
├── memory/
├── rules/
├── configuration/
├── .agent_assets/
│   ├── deerflow_skills/
│   └── skills/
├── MEMORY.md
├── tests/
└── config.json
```

## 运行命令

### 启动应用
```bash
python main.py
```

### 配置 API Key
```bash
echo "LLM_API_KEY=your_key" > .env
```

### 运行测试
```bash
./.venv/bin/python -B -m unittest discover -s tests -v
```

### 清理数据库与记忆
```bash
./clear_db.sh
```

## DeerFlow 接入约束

- DeerFlow 运行时配置由 `runtime/deerflow/` 下的适配层统一生成
- 运行期资产统一落到 `.runtime/deerflow/`
- DeerFlow skill 资产当前位于 `.agent_assets/deerflow_skills/public/`
- 财务部门角色定义与 DeerFlow agent 资产生成位于 `department/`
- 不要重新引入自研 `ToolLoopService`
- 不要重新创建 `llm/` 目录维持另一套聊天协议

## Skills 与 Tools

### DeerFlow 当前 skill

- `finance-core`
- `coordinator`
- `cashier`
- `bookkeeping`
- `policy-research`
- `tax`
- `audit`

### 本项目长期维护的领域 prompt 资产

- `.agent_assets/skills/accounting`
- `.agent_assets/skills/audit`
- `.agent_assets/skills/memory`
- `.agent_assets/skills/rules`
- `.agent_assets/skills/tax`

### 当前财务 tools

- `collaborate_with_department_role`
- `record_voucher`
- `query_vouchers`
- `record_cash_transaction`
- `query_cash_transactions`
- `calculate_tax`
- `audit_voucher`
- `store_memory`
- `search_memory`
- `reply_with_rules`

## 编码要求

### 导入

- 使用绝对导入
- 标准库、三方库、自定义模块分组

### 类型注解

- 公共函数与方法必须有参数和返回值类型
- 可空类型使用 `Optional[T]`

### Docstring

- 所有公共函数必须有 docstring
- docstring 需说明用途、参数、返回值、异常

### 注释

- 注释解释设计原因、边界和业务意图
- 不写“这里调用了函数”这类重复性注释

### 测试

- 改业务逻辑必须改对应测试
- 改 DeerFlow 接入层时，优先补：
  - 运行时资产测试
  - public client 接入测试
  - tool 注册测试
  - 会话边界测试

## 当前阶段禁止项

- 不要为了接 DeerFlow 再造一套自研 runtime
- 不要把 DeerFlow 内部模块当稳定 API 依赖
- 不要把运行期生成目录提交到远端
