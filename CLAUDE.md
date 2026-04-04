# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

智能财务部门 — 面向小企业财务场景的多 Agent 系统（毕业设计）。底层 agent runtime 使用 **DeerFlow public client**，财务业务逻辑（记账、审核、税务、出纳）由本项目自行维护。

## Commands

```bash
# 启动 CLI
python main.py

# 运行全部测试
./.venv/bin/python -B -m unittest discover -s tests -v

# 运行单个测试
./.venv/bin/python -B -m unittest tests.test_audit_service -v

# 清理数据库与记忆
./clear_db.sh

# 安装依赖
pip install -r requirements.txt
```

## Architecture

调用链路：`CLI → ConversationRouter → ConversationService → FinanceDepartmentService → 共享工作台/角色协作 → DeerFlowDepartmentRoleRuntimeRepository → DeerFlowClient → 财务工具/DeerFlow工具`

分层规则：`router → service → repository → model`，禁止跨层直接调用。

关键边界：
- `app/` — 启动入口与依赖装配（DI 容器、工厂），具体实现和第三方接入只在此层装配
- `conversation/` — 会话边界，用户可见响应收口
- `department/` — 财务部门主域：角色目录（`roles/`）、协作协议（`collaboration/`）、共享工作台（`workbench/`）
- `runtime/deerflow/` — DeerFlow 适配层，运行时资产生成到 `.runtime/deerflow/`（gitignored）
- `accounting/`, `cashier/`, `audit/`, `tax/`, `rules/` — 各业务特性模块，每个内部遵循 router/service/repository 分层
- `configuration/` — 配置读取与校验
- `.agent_assets/deerflow_skills/` — DeerFlow skill 资产；`.agent_assets/skills/` — 本项目领域 prompt 资产

存储：SQLite 业务仓储 + DeerFlow Native Memory/Checkpointer。

## Critical Rules

1. **DeerFlow 只走公开入口** — 允许依赖 `deerflow.client.DeerFlowClient`，禁止 deep import DeerFlow 内部模块
2. **代码必须带详细中文注释** — 解释设计原因、边界和业务意图，不写低价值注释
3. **按功能模块组织** — 不按 `services/`, `infrastructure/` 等横切目录扩展；一个文件一个类；禁止新增 `utils.py` / `helpers.py`
4. **错误处理** — 禁止裸 `except`；禁止向用户暴露第三方 runtime 细节；业务错误使用模块内异常类
5. **每次改动必须可验证** — 先读代码再改，改完补测试或更新测试，完成后重跑测试
6. **使用绝对导入** — 标准库、三方库、自定义模块分组
7. **公共函数必须有类型注解和 docstring**
8. **禁止项** — 不要再造自研 runtime/ToolLoopService/llm 目录；不要把 `.runtime/` 提交到远端

## Config

模型配置在 `config.json`，DeerFlow 风格 `default_model + models[]` 结构。API Key 通过 `.env` 注入（`MINIMAX_API_KEY` 等）。
