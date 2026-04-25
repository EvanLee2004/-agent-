# Changelog

## 最终版财务闭环后端

- 新增会计期间 `open/closed`，已结账期间禁止继续写入或修改凭证
- 凭证编号升级为期间内连续号 `JV-YYYYMM-0001`，并通过迁移兼容旧库
- 新增凭证过账、作废、红冲和更正能力；红冲通过反向凭证抵减，不删除原凭证
- 新增科目余额表、总账/明细账、试算平衡表和账簿完整性检查
- 新增 `schema_migrations` 与启动幂等迁移，集中管理 SQLite schema 演进
- 新增确定性业务 API：期间管理、凭证生命周期、报表、银行对账和银行流水入账建议
- API 错误统一返回 `error_code`、`message`、`request_id`、`details`
- 出纳对账要求关联已过账凭证，重复对账前必须先解除对账

## 生产级财务内核

- 启用受控 crewAI memory，本地存储到 `.runtime/crewai/memory`，并使用 `local_hash` embedding 避免默认外部 embedding 依赖
- 新增会话上下文服务，支持“刚才那张凭证”“上一笔”等引用解析，但金额、科目、状态仍必须通过工具查账确认
- 工具结果统一输出结构化 envelope，API 返回 `tool_results`、`context_refs`、`voucher_ids`、`audit_summary` 和 `errors`，不再从自然语言回复正则提取业务字段
- 将幂等记录从进程内缓存升级为 SQLite 持久化，降低服务重启后重复记账风险
- SQLite 初始化统一开启本地部署稳定配置，并新增备份/恢复服务
- 新增出纳/银行模块：`cashier-agent`、银行流水记录、查询和对账工具；出纳模块只维护资金流水，不直接修改总账
- 新增 deterministic 小公司账套 seed 生成器，覆盖正常凭证、重复入账、大额异常和无效凭证样例

## crewAI 会计部门迁移

- 将底层运行时替换为 `crewai==1.14.2`
- 产品边界收窄为纯会计核算
- 新增 `runtime/crewai/` 适配层与会计工具包装器
- 新增会计部门角色目录：`accounting-manager`、`voucher-accountant`、`ledger-reviewer`
- API 入口调整为 `api.accounting_app:app`
- 响应模型调整为 `reply_text`、`steps`、`voucher_ids`、`audit_summary`、`errors`
- 删除旧财务扩展模块、旧运行时适配层和不再使用的静态资产
- 迁移阶段 crewAI memory/cache 默认关闭，会计事实继续以 SQLite 为准
- 精简 app 装配层、运行时上下文和模型配置字段，删除不再承载业务边界的转发代码
