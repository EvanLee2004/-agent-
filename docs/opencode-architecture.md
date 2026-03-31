# OpenCode 架构详解

深入研究 opencode 源码后的完整架构文档。

---

## 1. OpenCode 配置目录结构

```
~/.config/opencode/
├── opencode.json          # 主配置（API providers, 模型配置）
├── package.json           # npm 依赖（@opencode-ai/plugin）
├── node_modules/          # 插件代码
│   └── @opencode-ai/plugin/
│       └── dist/          # TypeScript 编译后的 JS 代码
├── skills/               # 所有安装的 Skills（55个）
│   ├── senior-backend/
│   ├── code-reviewer/
│   ├── skill-security-auditor/
│   ├── skill-tester/
│   └── ...（共55个）
└── memory/              # 对话记忆
```

---

## 2. Skill 目录结构

```
skills/<skill-name>/
├── SKILL.md              # 必需：元数据 + SYSTEM_PROMPT
├── README.md             # 可选：使用说明
├── scripts/              # 可选：Python 工具脚本
│   ├── __init__.py
│   ├── script1.py        # 主脚本
│   └── script2.py
├── references/           # 可选：参考文档
└── assets/              # 可选：示例数据
```

---

## 3. SKILL.md 格式规范

### 3.1 Frontmatter (YAML)

```yaml
---
name: "skill-name"              # 必需：Skill 名称
description: "描述文字..."      # 必需：简短描述
compatibility: "opencode"      # 必需：兼容标识
version: "1.0.0"               # 可选：版本号
---
```

### 3.2 完整格式示例

```markdown
---
name: "senior-backend"
description: "Designs and implements backend systems..."
compatibility: opencode
---

# Senior Backend Engineer

## Quick Start

```bash
# 示例命令
python scripts/api_scaffolder.py openapi.yaml --framework express
```

## Tools Overview

### 1. API Scaffolder

**Input:** OpenAPI spec (YAML/JSON)
**Output:** Route handlers, validation middleware

## Backend Development Workflows

### API Design Workflow

1. Define resources...
2. Generate route scaffolding...
```

### 3.3 SYSTEM_PROMPT 提取

```python
pattern = r"## SYSTEM_PROMPT\s*\n(.+?)(?=\n##|\Z)"
match = re.search(pattern, skill_md, re.DOTALL)
return match.group(1).strip() if match else ""
```

---

## 4. Skill 加载机制

### 4.1 核心类：SkillLoader

```python
class SkillLoader:
    SKILLS_DIR = Path("skills")

    @classmethod
    def load(cls, skill_name: str) -> dict[str, Any]:
        """加载指定 Skill，返回 system_prompt 和路径"""
        skill_path = cls.SKILLS_DIR / skill_name
        skill_md_path = skill_path / "SKILL.md"
        skill_md = skill_md_path.read_text(encoding="utf-8")
        system_prompt = cls._extract_system_prompt(skill_md)
        
        return {
            "name": skill_name,
            "path": str(skill_path),
            "system_prompt": system_prompt,
            "scripts_dir": skill_path / "scripts",
        }
```

### 4.2 执行脚本：execute_script

```python
@classmethod
def execute_script(
    cls,
    skill_name: str,
    script_name: str,
    args: Optional[list[str]] = None,
    timeout: int = 30,
    env: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """通过 subprocess 执行 Skill 脚本"""
    # 构建命令
    script_path = Path(skill_info["scripts_dir"]) / f"{script_name}.py"
    cmd_args = [sys.executable, str(script_path)]
    if args:
        cmd_args.extend(args)
    
    # 合并环境变量
    exec_env = None
    if env:
        exec_env = os.environ.copy()
        exec_env.update(env)
    
    # 执行
    process = subprocess.run(
        cmd_args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=exec_env,
    )
    
    # 解析输出（JSON 或纯文本）
    if process.returncode == 0:
        try:
            output = json.loads(process.stdout)
        except json.JSONDecodeError:
            output = {"status": "ok", "message": process.stdout.strip()}
    else:
        output = {"status": "error", "message": process.stderr.strip()}
    
    return output
```

---

## 5. Agent 与 Skill 的关系

### 5.1 Agent 初始化时加载 SYSTEM_PROMPT

```python
# agents/accountant.py
class Accountant(BaseAgent):
    NAME = "accounting"

    def __init__(self):
        try:
            skill = SkillLoader.load(self.NAME)
            self.SYSTEM_PROMPT = skill["system_prompt"]
        except FileNotFoundError:
            self.SYSTEM_PROMPT = "你是记账专家，负责执行记账操作。"
```

### 5.2 Agent 调用 Skill 脚本

```python
# Agent 调用 Skill 脚本
result = SkillLoader.execute_script(
    "accounting",           # Skill 名称
    "execute",              # 脚本名称（不含 .py）
    [task, "--json"],       # 参数列表
    env={"LLM_API_KEY": os.environ.get("LLM_API_KEY", "")},
)
```

---

## 6. Skill 脚本标准格式

### 6.1 标准模板

```python
#!/usr/bin/env python3
"""Script Description

Usage:
    python script.py <task> [--json] [--feedback]

Examples:
    python script.py "任务描述"
    python script.py "任务描述" --json
"""

import argparse
import json
import os

from openai import OpenAI  # 只需 openai SDK

# 规则内联（不依赖外部文件）
MY_RULES = """
# 规则内容...
"""

def execute_task(task: str, feedback: str = "") -> dict:
    """执行任务主逻辑"""
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.minimax.chat/v1")
    model = os.environ.get("LLM_MODEL", "MiniMax-M2.7")
    
    # 构建 prompt...
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[...],
        temperature=0.3,
    )
    
    return {"status": "ok", "message": "...", "data": {...}}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--feedback", "-f", default="")
    args = parser.parse_args()
    
    result = execute_task(args.task, args.feedback)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result.get("message"))

if __name__ == "__main__":
    main()
```

### 6.2 关键设计原则

| 原则 | 说明 |
|------|------|
| **独立性** | Skill 脚本不依赖 core/ 模块 |
| **只用标准库** | 标准库 + openai SDK |
| **配置通过 env** | API key、base_url 等通过环境变量传递 |
| **规则内联** | 规则内容直接写在脚本里，不依赖外部文件 |
| **JSON 输出** | 支持 `--json` 参数输出 JSON 格式 |

---

## 7. 权限系统 (Permission System)

### 7.1 Hook 点定义

```typescript
export interface Hooks {
    // 权限请求拦截
    "permission.ask"?: (input: Permission, output: {
        status: "ask" | "deny" | "allow";
    }) => Promise<void>;
    
    // 工具执行前后
    "tool.execute.before"?: (input: {
        tool: string;
        sessionID: string;
        callID: string;
    }, output: { args: any }) => Promise<void>;
    
    "tool.execute.after"?: (input: {
        tool: string;
        sessionID: string;
        callID: string;
        args: any;
    }, output: {
        title: string;
        output: string;
        metadata: any;
    }) => Promise<void>;
}
```

### 7.2 Permission 类型

```typescript
type Permission = {
    permission: string;
    patterns: string[];
    always: string[];
    metadata: Record<string, any>;
};
```

---

## 8. 插件系统 (@opencode-ai/plugin)

### 8.1 工具定义

```typescript
import { tool } from "./tool.js";

export const ExamplePlugin = async (ctx) => {
    return {
        tool: {
            mytool: tool({
                description: "This is a custom tool",
                args: {
                    foo: tool.schema.string().describe("foo"),
                },
                async execute(args, context) {
                    return `Hello ${args.foo}!`;
                },
            }),
        },
    };
};
```

### 8.2 ToolContext

```typescript
type ToolContext = {
    sessionID: string;
    messageID: string;
    agent: string;
    directory: string;       // 当前项目目录
    worktree: string;        // 工作树根目录
    abort: AbortSignal;
    metadata(input: {...}): void;
    ask(input: AskInput): Promise<void>;
};
```

---

## 9. Tier 分类系统

| Tier | SKILL.md | Scripts | LOC |
|------|----------|---------|-----|
| BASIC | >=100行 | >=1 | 100-300 |
| STANDARD | >=200行 | 1-2 | 300-500 |
| POWERFUL | >=300行 | 2-3 | 500-800 |

---

## 10. 核心设计模式总结

### 10.1 Skill 独立性原则

```
✅ 正确做法：
- Skill 脚本只用标准库 + openai SDK
- 规则内联到脚本中
- 通过 subprocess env 参数传递配置

❌ 错误做法：
- from core.xxx import ...
- 依赖项目内部模块
- 硬编码配置
```

### 10.2 Agent-Skill 分离

| 概念 | 职责 | 位置 |
|------|------|------|
| Agent（角色） | 业务逻辑、流程控制、数据库读写 | agents/ |
| Skill（能力包） | 纯计算、LLM 调用、规则检查 | skills/ |

### 10.3 自然语言交互

- LLM 返回文本而非 JSON
- 解析通过正则表达式提取关键信息
- 降级处理：JSON 解析失败时返回纯文本

---

## 11. 关键文件路径

| 功能 | 路径 |
|------|------|
| Skill 加载器 | `core/skill_loader.py` |
| Agent 基类 | `agents/base.py` |
| Manager Agent | `agents/manager.py` |
| Accountant Agent | `agents/accountant.py` |
| Auditor Agent | `agents/auditor.py` |
| LLM 客户端 | `core/llm.py` |
| OpenCode 配置 | `~/.config/opencode/opencode.json` |
| OpenCode Skills | `~/.config/opencode/skills/` (55个skills) |
| 插件 SDK 类型 | `~/.config/opencode/node_modules/@opencode-ai/plugin/dist/` |

---

## 12. 我们的项目 vs OpenCode

| 方面 | OpenCode | 我们的项目 |
|------|---------|-----------|
| 运行环境 | CLI + AI Agent | CLI + AI Agent |
| Skill 调用 | 内置函数调用 | subprocess 脚本 |
| 提示词 | SYSTEM_PROMPT | SYSTEM_PROMPT |
| 工具执行 | 直接调用 | 脚本独立 |
| 权限控制 | Permission Hooks | 暂不需要 |
| 多 Agent | agenthub (worktree 隔离) | Manager 协调循环 |

---

## 附录：参考的 OpenCode Skills

研究过程中分析的 Skills：

| Skill | 用途 | 复杂度 |
|-------|------|--------|
| senior-backend | 后端开发 | Tier 3 |
| code-reviewer | 代码审查 | Tier 2 |
| skill-security-auditor | 安全审计 | Tier 2 |
| skill-tester | 测试生成 | Tier 2 |
| agent-designer | Agent 设计 | Tier 1 |
| frontend-design | 前端设计 | Tier 2 |
