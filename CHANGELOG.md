# Changelog

## crewAI 会计部门迁移

- 将底层运行时替换为 `crewai==1.14.2`
- 产品边界收窄为纯会计核算
- 新增 `runtime/crewai/` 适配层与会计工具包装器
- 新增会计部门角色目录：`accounting-manager`、`voucher-accountant`、`ledger-reviewer`
- API 入口调整为 `api.accounting_app:app`
- 响应模型调整为 `reply_text`、`steps`、`voucher_ids`、`audit_summary`、`errors`
- 删除旧财务扩展模块、旧运行时适配层和不再使用的静态资产
- crewAI memory/cache 初版默认关闭，会计事实继续以 SQLite 为准
