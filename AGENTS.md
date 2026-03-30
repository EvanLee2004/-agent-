# Agent Coding Guidelines

This is a Python project for a financial assistant CLI application that uses LLM APIs (MiniMax/DeepSeek) through the OpenAI SDK.

## Project Structure

```
.
├── main.py                 # CLI 入口
├── core/                   # 核心基础设施
│   ├── llm.py             # LLM 调用
│   └── session.py         # Session 管理（SQLite）
├── agents/                 # AI 角色
│   ├── assistant.py       # 基类
│   ├── manager.py         # 经理角色（分配任务）
│   └── assistants/         # 具体助手
│       ├── __init__.py
│       ├── expense.py      # 报销助手
│       ├── budget.py       # 预算助手
│       └── report.py       # 报表助手
├── sessions/              # SQLite 数据库目录
│   └── sessions.db        # 数据库文件
├── requirements.txt
└── .env
```

## Build/Lint/Test Commands

### Setup
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Running the Application
```bash
python main.py
```

### Linting (Ruff)
```bash
ruff check .
```

### Running a Single Test
```bash
pytest tests/test_filename.py::test_function_name -v
```

### Type Checking
```bash
mypy .
```

## Code Style Guidelines

### Python Version
- Python 3.12+ (uses type hints with built-in collection types like `list[dict]`)

### Type Hints
- Use type hints for all function parameters and return values
- Use `X | None` instead of `Optional[X]`
- Built-in collection types: `list[X]`, `dict[X, Y]`, `set[X]`

### Imports
- Standard library first, then third-party, then local
- Group imports by type with blank lines between groups

```python
import os
from enum import Enum
from openai import OpenAI
from dotenv import load_dotenv
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `ModelProvider`)
- Functions/variables: `snake_case` (e.g., `get_client`, `chat`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `PROVIDER_CONFIG`)
- Enum values: `UPPER_SNAKE_CASE` within enum class

### Error Handling
- Always wrap API calls and I/O operations in try/except blocks
- Provide meaningful error messages
- Let exceptions propagate for unrecoverable errors

```python
try:
    response = client.chat.completions.create(...)
except OpenAI.APIError as e:
    raise FinancialAssistantError(f"API call failed: {e}") from e
```

### Environment Variables
- Load from `.env` using `load_dotenv()` at module level
- Never hardcode API keys or secrets
- Access via `os.getenv("KEY_NAME")`

### Documentation
- Use docstrings for modules and public functions
- Chinese comments are acceptable for Chinese-speaking teams
- Keep comments updated when code changes

### Linting Configuration
- Ruff is used for linting
- Configure via `pyproject.toml` or `ruff.toml` in project root
- Recommended rules: E, F, I (errors, pyflakes, isort)

## Dependencies

- `openai` - OpenAI SDK (compatible with MiniMax/DeepSeek APIs)
- `python-dotenv` - Environment variable loading

## Environment Setup

Copy `.env.example` to `.env` and add your API keys:
```
MINIMAX_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
```

## Common Tasks

### Adding a New LLM Provider
1. Add enum value to `ModelProvider` (e.g., `DEEPSEEK = "deepseek"`)
2. Add provider config to `PROVIDER_CONFIG` dict with api_key, base_url, default_model
3. Test with `chat(..., provider=ModelProvider.NEW_PROVIDER)`

### Provider Config Example
```python
ModelProvider.DEEPSEEK: {
    "api_key": os.getenv("DEEPSEEK_API_KEY"),
    "base_url": "https://api.deepseek.com/v1",
    "default_model": "deepseek-chat",
},
```

### Running in Development
```bash
source .venv/bin/activate
python main.py
```
