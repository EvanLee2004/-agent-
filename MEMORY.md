# Long-Term Memory

长期稳定的用户偏好、事实和决策。

## 2026-04-04 Bug 修复

### 代码审查发现的问题

1. **tax/tax_service.py 第 128 行：else 分支死代码**
   - 第 127 行 `formula = "无需缴纳企业所得税"` 立即被第 128 行覆盖
   - 修复：删除第 128 行
   - 根因：拷贝粘贴 elif 公式时残留

2. **configuration/defaults.py：数据库路径重复定义**
   - `DEFAULT_ACCOUNTING_DB` 和 `DEFAULT_CASHIER_DB` 值完全相同
   - 修复：合并为 `DEFAULT_DB`，三个 SQLite 仓储统一引用

3. **department/collaboration/department_collaboration_service.py：Optional 导入**
   - 该文件第 26 行实际使用了 `Optional[str]`，review 说"未使用"不准确
   - 保留该导入

### 验证
- 66 个单元测试全部通过

## 2026-04-04 架构评审与重构

### 架构评审结论（P0/P1 问题）

1. **P0: 三库各自独立 initialize_storage 无原子性**
   - `ApplicationBootstrapper.initialize()` 改为单连接执行所有 CREATE TABLE
   - 中间失败自动回滚，不会留不一致状态

2. **P1: 工厂硬编码无法注入 mock**
   - `FinanceDomainServiceFactory.build()` / `ApplicationBootstrapperFactory.build()` 新增可选 repository 参数
   - 调用方可注入 mock 或不同实现，保留默认值向后兼容

3. **P1: DependencyContainer 名不副实**
   - 改名 `AppServiceFactory`，统一创建并复用三个 repository 实例
   - `ConversationRouterFactory` 改为接收 repository 参数注入

### 接口变更
- `ChartOfAccountsRepository` / `JournalRepository` / `CashierRepository` 新增 `database_path` 属性
- SQLite 实现暴露 `CREATE_*_TABLE_SQL` 模块级常量

### 测试覆盖
- 当前：66 个单元测试全部通过
- 新增：`test_cashier_service.py`, `test_chart_of_accounts_service.py`

## 2026-04-04 优化工作记录

### 已完成的CRITICAL优化

1. **企业所得税计算逻辑修复** (`tax/`)
   - 添加 `cost` 字段支持收入-成本计算应纳税所得额
   - 修复 `small_scale_vat_taxaxpayer` 别名拼写错误
   - 新增 13 个税务服务单元测试

2. **凭证重复检测逻辑** (`audit/`)
   - 添加详细注释解释 `==` 跳过自身逻辑的正确性
   - 新增 11 个审核服务单元测试

3. **全局可变状态移除** (`runtime/deerflow/`)
   - 使用 `contextvars.ContextVar` 替代类级别可变状态
   - 添加 `open_context_scope()` 上下文管理器
   - 保持线程/协程安全

4. **共享常量提取** (`configuration/`)
   - 新增 `configuration/defaults.py` 统一管理：
     - DB路径：`DEFAULT_ACCOUNTING_DB`, `DEFAULT_CASHIER_DB`
     - 金额阈值：`HIGH_AMOUNT_THRESHOLD`, `LOW_AMOUNT_THRESHOLD`
   - 消除多处硬编码重复

## engineering_rules
- 2026-04-02 用户提供的长期规则必须按类别分组存储，并且后续只按当前任务检索相关类别，禁止每次一次性全量加载所有规则。
- 2026-04-02 本项目后续所有改动都必须遵守统一工程规范：先规划后编码、先读后改、默认按安全生产代码标准处理、测试不可删不可跳、只做任务范围内必要改动。
- 2026-04-02 代码结构必须严格执行高可读性和软件工程约束：按功能模块组织，严格 router -> service -> repository -> model 分层，一个文件一个类，依赖外部注入，低耦合高内聚，禁止 utils/helpers 垃圾桶文件。
- 2026-04-02 命名和实现必须可读：名称表达用途，布尔值用 is/has/can 前缀，常量显式命名，禁止魔法数字；公开函数必须有 docstring，函数参数超过 3 个时改用 dataclass 或 schema 对象。
- 2026-04-02 注释只解释设计原因和业务意图，不解释代码表面行为；函数过长或需要注释解释”做什么”时必须继续拆分。
- 2026-04-02 错误处理必须捕获具体异常、错误向上层传递、业务错误使用自定义异常；禁止裸 except、禁止静默吞错、禁止不安全执行如 eval/exec/unsafe 反序列化。
- 2026-04-02 保持 DRY 和单一事实来源，重复逻辑必须抽取复用；在当前运行环境中，读/搜/测会使用现有终端与代码工具的等价能力，编辑统一走补丁工具，不假设不存在的 IDE 专用工具。
- 2026-04-02 做代码审查时必须采用安全优先视角：默认所有输入不可信，执行纵深防御、最小权限、失败安全原则，优先检查认证授权、输入校验、SQL/命令注入、密钥泄露、依赖风险、错误处理和日志暴露，并按 OWASP Top 10 与供应链安全清单输出可落地修复建议。

## database_rules
- 2026-04-02 处理数据库问题时按高级数据库工程师标准执行：SQL、schema 设计、查询优化和数据库架构都必须正确、可读、可解释；schema 不清楚时先确认，不猜表结构。
- 2026-04-02 写 SQL 时必须使用显式 JOIN，优先用 CTE 提升可读性，并在每个 CTE 上方写简短注释说明设计意图；别名统一短小小写，歧义列必须带表别名。
- 2026-04-02 做聚合前必须先确认结果粒度；使用窗口函数时明确 partition 和 ordering；使用递归 CTE 时必须写终止保护并说明递归边界。
- 2026-04-02 做 SQL 优化时按固定流程执行：先要 EXPLAIN 或 EXPLAIN ANALYZE，识别瓶颈，再给出具体索引或改写方案，同时说明收益和写放大、维护成本等副作用。
- 2026-04-02 数据库 schema 设计默认遵循 3NF，只有在明确性能理由下才反规范化；主键优先稳定代理键，列类型要精确，NOT NULL 作为默认，索引、外键和级联策略都要明确说明。
- 2026-04-02 数据库审查时必须主动检查常见反模式：函数包裹索引列、OFFSET 大分页、DISTINCT 掩盖错误 JOIN、相关子查询可改写但未改写、SELECT * 扩散到外层 JOIN。
- 2026-04-02 涉及 UPDATE、DELETE、TRUNCATE、DROP 等破坏性 SQL 时，必须先建议用 SELECT 校验影响范围，并显式标记风险。

## debugging_rules
- 2026-04-02 调试时必须采用系统化流程：先复现，再观察错误与症状，再提出 2-4 个可证伪假设，再做最小检查区分假设，最后定位根因、修复并解释原因；禁止凭直觉猜 bug。
- 2026-04-02 所有调试结论都必须基于实际代码、输出、堆栈、日志或可重复现象；如果无法复现，先明确缺失的是环境、输入、状态还是时序，而不是直接修改代码。
- 2026-04-02 调试坚持“一次只改一件事”，优先读代码和观测结果，再做最小变更；临时调试代码必须有明确目的，并在完成后移除。
- 2026-04-02 遇到性能、数据库、网络、并发、内存等问题时必须使用对应诊断手段：如 profiler、EXPLAIN ANALYZE、详细 traceback、锁或时序分析，而不是只凭表面症状判断。
- 2026-04-02 修复 bug 时必须说明根因、验证方式、回归风险，以及同类问题是否可能出现在别处；workaround 必须明确标注为临时方案。

## integration_architecture_rules
- 2026-04-02 设计系统集成时必须先明确源系统、目标系统、数据流方向、频率、延迟容忍度、体量和约束，再决定同步、异步或批处理模式；不允许在需求不清时直接拍脑袋选方案。
- 2026-04-02 集成模式优先选择标准开放协议，并显式解释取舍：REST/GraphQL 适合请求响应，队列或事件流适合高可靠异步处理，默认避免高频轮询作为首选。
- 2026-04-02 集成认证必须遵循最小权限原则，优先使用标准 OAuth 2.0 或 API Key 方案，并明确 token 存储、刷新、轮换和失效策略；禁止不安全地持久化凭据。
- 2026-04-02 集成必须设计明确的可靠性机制：幂等键、防重处理、指数退避加抖动、限流适配、熔断阈值、死信或人工升级路径，并假设外部 API 最长可用性中断 5 分钟。
- 2026-04-02 集成必须具备生产级可观测性：结构化日志、关联 ID、成功率/延迟/队列深度等指标、明确告警阈值，以及便于排查的 tracing/调试入口。
- 2026-04-02 输出集成方案时必须给出实施顺序、最高风险组件、关键伪代码或代码结构，并说明各步骤如何在不中断现有系统的前提下逐步落地。
