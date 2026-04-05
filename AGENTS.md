# Agent 开发指南

本文档面向在本仓库中工作的 AI Agent。面向财务场景的多 Agent 系统（毕业设计），底层 agent runtime 使用 **DeerFlow public client**，财务业务逻辑由本项目自行维护。

## 运行命令

```bash
# 启动应用
python main.py

# 配置 API Key
echo "MINIMAX_API_KEY=your_key" > .env

# 运行全部测试
./.venv/bin/python -B -m unittest discover -s tests -v

# 运行单个测试（推荐方式）
./.venv/bin/python -B -m unittest tests.test_audit_service -v

# 清理数据库与记忆
./clear_db.sh

# 安装依赖
pip install -r requirements.txt
```

## 架构原则

**调用链路**：`CLI / API → CliConversationHandler / AppConversationHandler → ConversationRouter → ConversationService → FinanceDepartmentService → DeerFlowDepartmentRoleRuntimeRepository → DeerFlowClient`  
`FinanceDepartmentService` 在调用 DeerFlow 后，会继续通过 `CollaborationStepFactory + DepartmentWorkbenchService` 完成协作摘要投影与历史持久化。

**分层规则**：`router → service → repository → model`，禁止跨层直接调用。

**关键边界**：
- `app/` — 启动入口与依赖装配（DI 容器、工厂），具体实现和第三方接入只在此层装配
- `conversation/` — 会话边界，用户可见响应收口
- `department/` — 财务部门主域：角色目录（`roles/`）、协作协议（`collaboration/`）、协作工作台（`workbench/`，负责 execution_events / collaboration_steps 持久化与查询）
- `runtime/deerflow/` — DeerFlow 适配层，运行时资产生成到 `.runtime/deerflow/`（gitignored）
- `accounting/`、`cashier/`、`audit/`、`tax/`、`rules/` — 各业务特性模块，内部遵循 router/service/repository 分层
- `configuration/` — 配置读取与校验

**DeerFlow 约束**：只依赖 `deerflow.client.DeerFlowClient`；禁止 deep import DeerFlow 内部模块；不要造自研 runtime/ToolLoopService/llm 目录

**运行时说明**：
- API 默认共享 `.runtime/api` 作为进程级 runtime_root，不同 `thread_id` 依赖 DeerFlow checkpoint 自动隔离
- `os.environ` 快照恢复只缩小污染窗口，不保证多线程并发安全
- 当前部署建议：`uvicorn --workers 1`

## 代码风格

### 导入
- 使用绝对导入（`from app.cli_router import CliRouter`）
- 分组顺序：标准库 → 三方库 → 自定义模块

### 类型注解
- 公共函数与方法必须有参数和返回值类型
- 可空类型使用 `Optional[T]`
- 示例：`def record_voucher(voucher: Voucher) -> VoucherId: ...`

### Docstring
- 所有公共函数必须有 docstring
- 说明用途、参数、返回值、异常

### 注释
- 注释解释**为什么**这样设计、边界在哪里、为什么不能简化
- 不写"给变量赋值"这类低价值注释
- 示例：`# 使用 round 而非 floor，因为税务场景要求四舍五入到分`

### 命名
- 类名：`PascalCase`（如 `AuditService`）
- 函数/变量：`snake_case`（如 `query_vouchers`）
- 常量：`UPPER_SNAKE_CASE`
- 私有成员：前缀 `_`

### 错误处理
- **禁止裸 `except`**：必须捕获具体异常类型
- **禁止向用户暴露第三方 runtime 细节**：业务错误使用模块内异常类
- 示例：
  ```python
  except VoucherNotFoundError:
      raise
  except Exception as e:
      raise AuditError(f"审核失败：{e}") from e
  ```

## 组织原则

- **按功能模块组织**：不按 `services/`、`infrastructure/` 等横切目录扩展
- **一个文件一个类**：为默认原则
- **禁止新增** `utils.py` / `helpers.py`

## 测试要求

- 改业务逻辑必须改对应测试
- 改 DeerFlow 接入层时，优先补：
  - 运行时资产测试
  - public client 接入测试
  - tool 注册测试
  - 会话边界测试
- 单个测试：`.venv/bin/python -B -m unittest tests.test_audit_service -v`

## 配置

- 模型配置在 `config.json`，DeerFlow 风格 `default_model + models[]` 结构
- API Key 通过 `.env` 注入（`MINIMAX_API_KEY` 等）
- 运行期生成目录 `.runtime/deerflow/` 已 gitignore，不提交到远端

## 当前财务工具

- `generate_fiscal_task_prompt`（复杂多步任务专用，通过 FiscalRolePromptBuilder 生成结构化财务专业 prompt）
- `record_voucher`、`query_vouchers`
- `record_cash_transaction`、`query_cash_transactions`
- `calculate_tax`、`audit_voucher`、`reply_with_rules`
