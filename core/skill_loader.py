"""Skill 加载器，按 opencode 规范。

负责：
1. 读取 SKILL.md 提取 SYSTEM_PROMPT
2. 执行 scripts/*.py 脚本（通过 subprocess）
3. 管理 Skill 的元数据
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

    按 opencode 规范加载和管理 Skill：
    - 读取 SKILL.md 提取提示词
    - 通过 subprocess 执行 scripts/ 下的脚本
    - 支持 --json 输出格式

    Attributes:
        SKILLS_DIR: Skill 根目录路径
    """

    SKILLS_DIR = Path("skills")

    @classmethod
    def load(cls, skill_name: str) -> dict[str, Any]:
        """加载指定 Skill。

        Args:
            skill_name: Skill 名称（对应目录名）

        Returns:
            包含 Skill 信息的字典：
            {
                "name": str,
                "path": str,
                "system_prompt": str,
                "scripts_dir": Path
            }

        Raises:
            FileNotFoundError: Skill 目录或 SKILL.md 不存在
            ValueError: SKILL.md 格式错误
        """
        skill_path = cls.SKILLS_DIR / skill_name

        if not skill_path.exists():
            raise FileNotFoundError(f"Skill '{skill_name}' not found at {skill_path}")

        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md not found at {skill_md_path}")

        skill_md = skill_md_path.read_text(encoding="utf-8")
        system_prompt = cls._extract_system_prompt(skill_md)

        if not system_prompt:
            raise ValueError(f"Failed to extract SYSTEM_PROMPT from SKILL.md")

        return {
            "name": skill_name,
            "path": str(skill_path),
            "system_prompt": system_prompt,
            "scripts_dir": skill_path / "scripts",
        }

    @classmethod
    def execute_script(
        cls,
        skill_name: str,
        script_name: str,
        args: Optional[list[str]] = None,
        timeout: int = 30,
        env: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """执行 Skill 的脚本。

        通过 subprocess 调用独立脚本，支持 JSON 输出。

        Args:
            skill_name: Skill 名称
            script_name: 脚本名称（不含 .py）
            args: 命令行参数列表
            timeout: 超时时间（秒）
            env: 传递给脚本的环境变量字典

        Returns:
            执行结果字典：
            {
                "status": "ok" | "error",
                "message": str,
                "data": dict | None (可选)
            }

        Raises:
            FileNotFoundError: 脚本不存在
            subprocess.TimeoutExpired: 执行超时
        """
        try:
            skill_info = cls.load(skill_name)
        except FileNotFoundError:
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
                    elif isinstance(output, dict):
                        if "status" not in output:
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
        except Exception as e:
            output = {"status": "error", "message": str(e)}

        return output

    @classmethod
    def get_skill_names(cls) -> list[str]:
        """获取所有可用的 Skill 名称。

        Returns:
            Skill 名称列表
        """
        if not cls.SKILLS_DIR.exists():
            return []
        return [
            d.name
            for d in cls.SKILLS_DIR.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ]

    @staticmethod
    def _extract_system_prompt(skill_md: str) -> str:
        """从 SKILL.md 提取 SYSTEM_PROMPT。

        Args:
            skill_md: SKILL.md 文件内容

        Returns:
            SYSTEM_PROMPT 文本，如果未找到则返回空字符串
        """
        pattern = r"## SYSTEM_PROMPT\s*\n(.+?)(?=\n##|\Z)"
        match = re.search(pattern, skill_md, re.DOTALL)
        return match.group(1).strip() if match else ""
