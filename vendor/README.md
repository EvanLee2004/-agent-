# vendor/deer-flow — DeerFlow 上游子模块

本目录当前不是“手工复制进仓库的一份源码”，而是通过 git submodule 接入的
DeerFlow 上游仓库。项目运行时通过 editable install 加载其中的
`backend/packages/harness`，作为 `deerflow` Python 包的实际来源。

## 当前接入方式

当前仓库中的接线方式如下：

1. `.gitmodules` 声明 `vendor/deer-flow` 子模块，指向上游 DeerFlow 仓库
2. `requirements.txt` 使用 `-e ./vendor/deer-flow/backend/packages/harness`
3. 本项目业务主链路只依赖 `deerflow.client.DeerFlowClient` 等公开包入口，
   不直接把 `vendor/deer-flow/` 当作业务目录来 import

这样做的原因是：
- 保留上游源码形态，后续同步上游更直接
- 避免“复制源码后本地魔改”导致来源不清
- 让 smoke test 能直接验证当前安装形态下的 DeerFlow 模块可导入

## 本目录的角色

`vendor/deer-flow/` 在本项目里承担三类职责：

1. 作为 `deerflow` Python 包的安装来源
2. 作为 `tests/test_vendor_deerflow_smoke.py` 的导入验证对象
3. 作为必要时查看上游实现细节的参考副本

业务主链路依然在 `runtime/deerflow/`：
- `runtime/deerflow/`：本项目的 DeerFlow 适配层，负责把 DeerFlow public client
  桥接到财务部门、工作台和请求级工具上下文
- `vendor/deer-flow/`：上游源码来源，不负责本项目业务装配

## 与现有 runtime/deerflow 的关系

两者职责必须严格区分：
- `vendor/deer-flow/`：上游源码与安装来源
- `runtime/deerflow/`：本项目适配层

不要把 `vendor/deer-flow/` 当作业务主路径依赖注入点；除非任务明确要求修改 vendor，
否则项目重构应优先落在 `runtime/deerflow/`、`department/`、`conversation/` 和 `app/`。
