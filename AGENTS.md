# Agent 开发指南

本文档面向 AI Agent，为在此代码库中开发提供指导。

## 项目概述

智能会计是一个单 Agent 系统，基于 LLM 驱动的智能助手，处理记账、查询和智能对话任务。

```
用户 → 智能会计 → LLM 判断意图 → 执行/回复
```

## 运行命令

### 启动应用
```bash
python main.py
```

### 手动配置（如需要）
```bash
# 设置 API 密钥
echo "LLM_API_KEY=your_key" > .env

# 运行应用
python main.py
```

### Skill 脚本
```bash
# 记账 Skill
python skills/accounting/scripts/execute.py "报销1000元" --json

# 审核 Skill
python skills/audit/scripts/execute.py "[ID:1] 支出1000元" --json
```

### 数据库
```bash
# 清除账目数据
./clear_db.sh
# 或直接删除
rm data/ledger.db
```

### 依赖安装
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 架构改进

### 核心优化（已实施）

| 优化项 | 文件 | 说明 |
|--------|------|------|
| P0-A | `infrastructure/llm.py` | LLM 调用重试机制（3次）+ 异常处理 + 超时控制 |
| P0-B | `agents/accountant_agent.py` | 结构化 JSON 输出替代正则匹配，支持 fallback |
| P1-A | `agents/accountant_agent.py` | 依赖注入解耦，AccountantAgent 类 |
| P1-B | `agents/accountant_agent.py` | Skill 系统集成到主流程 |
| P2-A | `infrastructure/ledger_repository.py` | Repository 模式抽象数据库层 |
| P2-B | `providers/config.py` | 配置验证层，启动时校验配置完整性 |

### LLM 调用特性（llm.py）

```python
# chat() 方法特性
LLMResponse = llm_client.chat(
    messages,           # 对话消息
    temperature=0.3,    # 温度参数
    max_retries=3,      # 最大重试次数
    timeout=30,         # 超时秒数
)

# LLMResponse 结构
@dataclass
class LLMResponse:
    content: str           # 响应内容
    usage: dict           # token 使用量
    model: str            # 使用的模型
    success: bool         # 是否成功
    error_message: str     # 错误信息（失败时）
```

### 意图识别（accountant_agent.py）

```python
# 支持的意图格式
{"intent": "accounting", "data": {"date": "...", "amount": 500, "type": "支出", "description": "..."}}
{"intent": "query", "data": {"date": "2024-01"}}
{"intent": "chat", "data": {"reply": "你好！"}}

# 解析优先级：JSON > 正则 fallback
parsed = parse_intent(llm_response)
```

### Agent 类（accountant_agent.py）

```python
# 推荐：使用依赖注入
agent = AccountantAgent(llm_client=llm_client)
result = await agent.handle(user_input)

# 向后兼容：模块级函数
result = await handle(user_input)
```

### Repository 模式（ledger_repository.py）

```python
# 接口
class ILedgerRepository(ABC):
    def init_db() -> None
    def write(...) -> int
    def get(...) -> list[dict]
    def update_status(...) -> None
    def get_by_id(...) -> Optional[dict]

# 使用
from infrastructure.ledger_repository import SQLiteLedgerRepository
repo = SQLiteLedgerRepository()
```

### 配置验证（providers/config.py）

```python
# ConfigValidator.validate() 检查：
# 1. 必需字段完整性 (provider, model, base_url)
# 2. provider 是否支持
# 3. model 是否在 provider 的模型列表中

result = ConfigValidator.validate(config)
if not result.is_valid:
    print(result.error_message)  # 明确的错误信息
```

## 代码风格

### 1. 导入（Imports）

- 使用绝对导入，基于项目根目录
- 三方库在前，标准库在中，自定义模块在后
- 每组之间空一行

```python
# 标准库
import json
import os
from pathlib import Path
from typing import Optional

# 三方库
from dotenv import load_dotenv
from openai import OpenAI

# 自定义模块
from infrastructure.llm import LLMClient
from infrastructure.ledger import write_entry
```

### 2. 类型注解

- 函数参数和返回值必须标注类型
- 使用 `Optional[T]` 表示可空类型，而非 `T | None`

```python
def get_entries(
    date: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    ...
```

### 3. 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 类名 | PascalCase | `LLMClient`, `ProviderConfig` |
| 函数/变量 | snake_case | `get_entries`, `anomaly_flag` |
| 常量 | UPPER_SNAKE_CASE | `LEDGER_DB`, `DEFAULT_MEMORY_LIMIT` |
| 私有属性 | _前缀 | `_instance` |

### 4. Docstrings

所有公共函数必须有 docstring，说明参数和返回值。

```python
def write_entry(
    datetime: str,
    type_: str,
    amount: float,
    description: str,
    recorded_by: str = "accountant",
    anomaly_flag: Optional[str] = None,
    anomaly_reason: Optional[str] = None,
) -> int:
    """写入账目条目

    Args:
        datetime: 日期时间，格式 YYYY-MM-DD HH:MM:SS
        type_: 类型，收入/支出
        amount: 金额（正数）
        description: 描述说明
        recorded_by: 记录人
        anomaly_flag: 异常标识（可选）
        anomaly_reason: 异常原因（可选）

    Returns:
        新建条目的 ID
    """
```

### 5. dataclass 使用

配置类使用 `@dataclass` 装饰器：

```python
@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    usage: dict
    model: str
```

### 6. 错误处理

- 使用明确异常类型，不捕获宽泛异常
- 敏感信息不暴露在错误消息中

```python
# 正确
try:
    return json.loads(CONFIG_FILE.read_text())
except (json.JSONDecodeError, IOError):
    return None
```

### 7. 字符串处理

- 使用 f-string 进行格式化
- 敏感操作后及时清理

```python
result = f"记账成功 [ID:{entry_id}]"
if info.get("anomaly_reason"):
    result += f"（{info['anomaly_reason']}）"
```

### 8. 异步代码

使用 `async/await` 模式，保持一致性：

```python
async def handle(user_input: str) -> str:
    ...
    reply = await handle(user_input)
```

## 项目结构

```
├── main.py                      # CLI 入口
├── agents/
│   └── accountant_agent.py      # 智能会计主模块（AccountantAgent 类）
├── infrastructure/
│   ├── llm.py                  # LLM 调用封装（重试+异常处理）
│   ├── ledger.py               # 数据库接口（向后兼容）
│   ├── ledger_repository.py    # Repository 模式实现
│   ├── memory.py               # 长期记忆系统
│   └── skill_loader.py        # Skill 加载器
├── providers/
│   ├── __init__.py            # Provider 配置定义
│   └── config.py             # 配置管理（含验证层）
├── skills/                     # 技能目录（扁平结构）
│   ├── docx/                   # Word 文档处理（Anthropic 官方）
│   ├── pdf/                     # PDF 文档处理（Anthropic 官方）
│   ├── pptx/                    # PPT 演示文稿处理（Anthropic 官方）
│   ├── xlsx/                    # Excel 电子表格处理（Anthropic 官方）
│   ├── rules/                   # 中国会计准则
│   ├── tax/                    # 中国税务（待开源替代）
│   ├── audit/                   # 账目审核
│   ├── accounting/              # 智能记账
│   └── accounting/reference/    # 参考资料（Beancount, IFRS）
├── memory/                     # 记忆存储（JSON）
├── data/                       # 账目数据库（SQLite）
└── config.json                # 模型配置
```

## 技能系统（Skills）

### 概述

技能系统基于 SkillLoader 实现，支持意图分流和独立执行。每个 Skill 包含：
- `SKILL.md`：技能定义，包含 `## SYSTEM_PROMPT` 标记的系统提示
- `scripts/`：可选的执行脚本目录

### 技能分类

#### 文档处理类（documents/）

| 技能 | 用途 | 来源 |
|------|------|------|
| docx | Word 文档处理（创建、编辑、提取内容） | Anthropic 官方 |
| pdf | PDF 处理（提取文本、合并、分割） | Anthropic 官方 |
| pptx | PowerPoint 演示文稿处理 | Anthropic 官方 |
| xlsx | Excel 电子表格处理 | Anthropic 官方 |

#### 会计专业类（accounting/）

| 技能 | 用途 | 来源 |
|------|------|------|
| rules | 中国企业会计准则参考 | 自定义 v2.0 |
| tax | 中国税务处理 | **待开源替代** |
| audit | 账目审核 | 模板 |
| accounting | 智能记账执行 | 模板 |

### 技能目录规范

```
skills/                           # 扁平结构，所有技能在同一层级
├── docx/                        # Word 处理
│   ├── SKILL.md                # 技能定义
│   └── scripts/                # 可选脚本
├── pdf/                         # PDF 处理
├── pptx/                        # PPT 处理
├── xlsx/                        # Excel 处理
├── rules/                       # 中国会计准则
├── tax/                         # 中国税务（待开源替代）
├── audit/                       # 账目审核
├── accounting/                  # 智能记账
└── accounting/reference/        # 参考资料（只读）
    ├── beancount/              # Beancount 复式记账
    └── ifrs/                   # IFRS 国际准则
```

### SkillLoader 系统提示提取

SkillLoader 使用正则表达式提取系统提示：
```python
r"## SYSTEM_PROMPT\s*\n(.+?)(?=\n##|\Z)"
```

所有自定义技能 **必须** 包含 `## SYSTEM_PROMPT` 标记，否则无法被加载。

### Anthropic 官方技能

Anthropic 官方技能库（https://github.com/anthropic/skills）提供企业级文档处理能力：
- **docx**：Word 文档创建、编辑、内容提取
- **pdf**：PDF 文本提取、合并、分割、OCR
- **pptx**：PowerPoint 创建、编辑
- **xlsx**：Excel 数据处理、公式计算

> 注意：Anthropic 官方技能为专有软件，仅供毕业项目参考使用。

### 中国税务技能（tax）

中国税务技能目前处于 **模板占位** 状态，等待开源替代品。未找到中国税务相关的开源 AI Skill，如有任何发现请及时更新。

功能范围（待实现）：
- 增值税（VAT）处理
- 企业所得税计算
- 个人所得税代扣代缴
- 税务申报合规检查
- 发票验证与管理

## 核心模块 API

### ledger.py
- `init_ledger_db()` - 初始化数据库
- `write_entry(...)` - 写入账目，返回 ID
- `get_entries(...)` - 查询账目列表
- `update_entry_status(...)` - 更新状态

### ledger_repository.py
- `SQLiteLedgerRepository` - SQLite 实现
- `ILedgerRepository` - 抽象接口
- `get_ledger_repository()` - 获取单例实例

### memory.py
- `read_memory(agent_name)` - 读取记忆
- `write_memory(agent_name, memory)` - 写入记忆
- `add_experience(agent_name, exp)` - 添加经验
- `get_memory_context(agent_name)` - 获取格式化上下文

### llm.py
- `LLMClient.get_instance()` - 获取单例
- `client.chat(messages, ...)` - 发送对话请求（支持重试）

## 业务规则

### 记账异常标注
- 金额 > 50000：标注"需审核"
- 金额 < 10：标注"金额过小"

### 账目状态
- `pending`：待审核
- `approved`：已通过

### 记忆限制
- 每个 Agent 最多保留 20 条经验（DEFAULT_MEMORY_LIMIT * 2）
- 超过后截断保留最新

## Git 约定

```
# 忽略的文件
.env              # API 密钥
__pycache__/      # Python 缓存
*.pyc             # 编译文件
.venv/            # 虚拟环境
*.db              # 数据库
data/             # 数据目录
sessions/         # 会话目录
```
