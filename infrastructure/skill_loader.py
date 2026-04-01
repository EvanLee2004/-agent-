"""Skill Loader 模块。

该实现尽量向 OpenCode 的 Skill 约定对齐：
- 优先从 `.opencode/skills/` 发现 Skill
- 同时兼容 `.claude/skills/`、`.agents/skills/`
- 为了兼容当前项目历史结构，也保留根目录 `skills/` 作为回退路径

在调用范式上，本模块遵循“Prompt 优先、脚本可选”：
- Skill 的主能力来自 `SKILL.md`
- `scripts/` 下的脚本只是辅助工具，不应替代主 LLM 流程

Example:
    skill_info = SkillLoader.load("accounting")
    system_prompt = SkillLoader.load_system_prompt("accounting")
    result = SkillLoader.execute_script("docx", "accept_changes", ["file.docx"])
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


class SkillLoader:
    """Skill 加载器。

    设计目标：
    1. 让主 Agent 通过 `SKILL.md` 注入领域能力。
    2. 让脚本执行退居为“需要时才用的辅助能力”。
    3. 在目录发现上尽量贴近 OpenCode，同时兼容当前项目已有结构。
    """

    # 目录顺序体现“先贴近 OpenCode，再兼容旧结构”的策略。
    # 未来如果你把 Skill 迁移到 `.opencode/skills/`，业务代码无需修改。
    SKILL_DIR_CANDIDATES = [
        Path(".opencode/skills"),
        Path(".claude/skills"),
        Path(".agents/skills"),
        Path("skills"),
    ]

    @classmethod
    def load(cls, skill_name: str) -> dict[str, Any]:
        """按名称加载 Skill，并提取其核心提示词。

        提取逻辑兼容两种写法：
        1. 当前项目旧写法：`## SYSTEM_PROMPT` 段落保存核心提示词
        2. OpenCode 常见写法：frontmatter 之后的正文整体就是 Skill 内容

        Args:
            skill_name: Skill 名称。

        Returns:
            包含 Skill 名称、路径、主提示词和脚本目录的字典。

        Raises:
            FileNotFoundError: 未在支持的目录中找到该 Skill。
            ValueError: 找到了 Skill，但未能从 `SKILL.md` 中提取有效提示词。
        """
        skill_path = cls._find_skill_path(skill_name)
        if skill_path is None:
            raise FileNotFoundError(
                f"Skill '{skill_name}' not found in supported skill directories"
            )

        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md not found at {skill_md_path}")

        skill_md = skill_md_path.read_text(encoding="utf-8")
        system_prompt = cls._extract_prompt_text(skill_md)

        if not system_prompt:
            raise ValueError(f"Failed to extract prompt content from {skill_md_path}")

        return {
            "name": skill_name,
            "path": str(skill_path),
            "system_prompt": system_prompt,
            "scripts_dir": skill_path / "scripts",
        }

    @classmethod
    def load_system_prompt(cls, skill_name: str) -> str:
        """只读取 Skill 的主提示词。

        Args:
            skill_name: Skill 名称。

        Returns:
            适合直接注入到 LLM system message 的文本内容。
        """
        return cls.load(skill_name)["system_prompt"]

    @classmethod
    def execute_script(
        cls,
        skill_name: str,
        script_name: str,
        args: Optional[list[str]] = None,
        timeout: int = 30,
        env: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """通过 subprocess 执行 Skill 的辅助脚本。

        注意：
        这个接口保留给文档处理、文件转换等“工具型 Skill”使用。
        对业务类 Skill 来说，首选调用方式仍然是 `load_system_prompt()`。

        Args:
            skill_name: Skill 名称。
            script_name: 脚本名，不带 `.py` 后缀。
            args: 传入脚本的命令行参数列表。
            timeout: 超时时间，单位秒。
            env: 额外传给子进程的环境变量。

        Returns:
            统一格式的执行结果字典。
        """
        try:
            skill_info = cls.load(skill_name)
        except (FileNotFoundError, ValueError):
            return {"status": "error", "message": f"Skill '{skill_name}' not found"}

        script_path = Path(skill_info["scripts_dir"]) / f"{script_name}.py"
        if not script_path.exists():
            return {
                "status": "error",
                "message": f"Script not found: {script_path}",
            }

        cmd_args = [sys.executable, str(script_path)]
        if args:
            cmd_args.extend(args)

        exec_env = None
        if env:
            exec_env = os.environ.copy()
            exec_env.update(env)

        try:
            process = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=exec_env,
            )

            if process.returncode == 0:
                try:
                    output = json.loads(process.stdout)
                    if isinstance(output, str):
                        output = {"status": "ok", "message": output}
                    elif isinstance(output, dict) and "status" not in output:
                        output = {"status": "ok", "data": output}
                except json.JSONDecodeError:
                    output = {
                        "status": "ok",
                        "message": process.stdout.strip(),
                    }
            else:
                error_msg = process.stderr.strip() or process.stdout.strip()
                output = {
                    "status": "error",
                    "message": error_msg
                    or f"Script exited with code {process.returncode}",
                    "returncode": process.returncode,
                }
        except subprocess.TimeoutExpired:
            output = {
                "status": "error",
                "message": f"Script timeout after {timeout}s",
            }
        except Exception as exc:
            output = {"status": "error", "message": str(exc)}

        return output

    @classmethod
    def get_skill_names(cls) -> list[str]:
        """列出当前可发现的 Skill 名称。"""
        skill_names: set[str] = set()

        for skill_dir in cls.SKILL_DIR_CANDIDATES:
            if not skill_dir.exists():
                continue

            for path in skill_dir.iterdir():
                if path.is_dir() and (path / "SKILL.md").exists():
                    skill_names.add(path.name)

        return sorted(skill_names)

    @classmethod
    def _find_skill_path(cls, skill_name: str) -> Optional[Path]:
        """在多个候选目录中查找 Skill 路径。

        Args:
            skill_name: Skill 名称。

        Returns:
            找到则返回 Skill 目录路径，找不到返回 None。
        """
        for skill_dir in cls.SKILL_DIR_CANDIDATES:
            candidate = skill_dir / skill_name
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _extract_prompt_text(skill_md: str) -> str:
        """从 `SKILL.md` 中提取主提示词。

        提取顺序：
        1. 如果存在 `## SYSTEM_PROMPT`，优先使用该段内容。
        2. 否则，使用 frontmatter 之后的整个正文。

        这样既兼容当前项目，也更贴近 OpenCode 对 Skill 正文的使用方式。

        Args:
            skill_md: `SKILL.md` 原始文本。

        Returns:
            可作为 system message 使用的文本；失败返回空字符串。
        """
        system_prompt_pattern = r"## SYSTEM_PROMPT\s*\n(.+?)(?=\n##|\Z)"
        match = re.search(system_prompt_pattern, skill_md, re.DOTALL)
        if match:
            return match.group(1).strip()

        body = SkillLoader._strip_frontmatter(skill_md)
        return body.strip()

    @staticmethod
    def _strip_frontmatter(skill_md: str) -> str:
        """移除 YAML frontmatter，返回正文部分。

        OpenCode 的 Skill 常在文件开头使用 frontmatter 描述 `name`、
        `description` 等元信息。这里不强制解析这些字段，只负责剥离它们，
        让正文可以直接作为提示词来源。

        Args:
            skill_md: `SKILL.md` 原始文本。

        Returns:
            去掉 frontmatter 后的正文。
        """
        frontmatter_pattern = r"^---\s*\n.*?\n---\s*\n?"
        return re.sub(frontmatter_pattern, "", skill_md, count=1, flags=re.DOTALL)
