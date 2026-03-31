"""Skill Loader Module - Loads and executes Skills per opencode specification.

This module implements the Skill loading mechanism for the financial
assistant application, following opencode's convention where:
- Each Skill resides in a dedicated directory under skills/
- Each Skill contains a SKILL.md file with metadata and SYSTEM_PROMPT
- Skill capabilities are exposed via executable scripts in scripts/

The loader provides:
1. Loading Skill metadata and SYSTEM_PROMPT from SKILL.md
2. Executing Skill scripts via subprocess with isolation
3. Supporting JSON output format for structured data exchange

Example:
    skill_info = SkillLoader.load("accounting")
    result = SkillLoader.execute_script("accounting", "execute", ["task", "--json"])
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


class SkillLoader:
    """Skill loader and executor following opencode conventions.

    The SkillLoader provides a unified interface for loading Skill
    metadata and executing Skill scripts. Each Skill operates in
    isolation via subprocess, receiving input via CLI arguments and
    environment variables.

    Attributes:
        SKILLS_DIR: Root directory containing all Skill directories.

    Example:
        skill = SkillLoader.load("accounting")
        print(skill["system_prompt"])  # Access loaded system prompt

        result = SkillLoader.execute_script(
            "accounting",
            "execute",
            ["reimburse 1000 travel", "--json"]
        )
    """

    SKILLS_DIR = Path("skills")

    @classmethod
    def load(cls, skill_name: str) -> dict[str, Any]:
        """Load a Skill by name and extract its metadata.

        Reads the SKILL.md file from the Skill directory and extracts
        the SYSTEM_PROMPT section using regex. The SKILL.md must contain
        a "## SYSTEM_PROMPT" section.

        Args:
            skill_name: Name of the Skill directory to load (e.g.,
                "accounting", "audit", "coordination").

        Returns:
            Dictionary containing:
                - name: Skill name (same as input)
                - path: Absolute path to Skill directory
                - system_prompt: Extracted SYSTEM_PROMPT text
                - scripts_dir: Path to Skill's scripts directory

        Raises:
            FileNotFoundError: If the Skill directory or SKILL.md
                does not exist.
            ValueError: If SYSTEM_PROMPT cannot be extracted from
                SKILL.md (missing "## SYSTEM_PROMPT" section).
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
        """Execute a Skill script via subprocess.

        Runs the specified script with given arguments in an isolated
        subprocess. The script receives environment variables for
        sensitive data (e.g., API keys). Output is parsed as JSON
        if available, otherwise returned as plain text.

        Args:
            skill_name: Name of the Skill containing the script.
            script_name: Script filename without .py extension
                (e.g., "execute", "intent").
            args: Optional list of CLI arguments to pass to script.
            timeout: Execution timeout in seconds. Defaults to 30.
            env: Optional dict of environment variables to pass to
                the subprocess. Merged with current environment.

        Returns:
            Dictionary with execution results:
                - status: "ok" on success, "error" on failure
                - message: Human-readable status or error message
                - data: Parsed JSON output (if script returned JSON)
                - returncode: Exit code (only on error)

            On success (status="ok"), one of message or data is present.
            On error (status="error"), message describes the failure.

        Raises:
            FileNotFoundError: If the skill or script does not exist.
            subprocess.TimeoutExpired: If script exceeds timeout
                (caught and returned as error status).
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
        """List all available Skill names.

        Scans the SKILLS_DIR for directories containing SKILL.md
        and returns their names.

        Returns:
            List of Skill directory names that have a SKILL.md file.
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
        """Extract SYSTEM_PROMPT content from SKILL.md text.

        Uses regex to find the section starting with "## SYSTEM_PROMPT"
        and returns its content until the next section or end of file.

        Args:
            skill_md: Raw text content of SKILL.md file.

        Returns:
            The SYSTEM_PROMPT section content, stripped of whitespace.
            Empty string if "## SYSTEM_PROMPT" section not found.
        """
        pattern = r"## SYSTEM_PROMPT\s*\n(.+?)(?=\n##|\Z)"
        match = re.search(pattern, skill_md, re.DOTALL)
        return match.group(1).strip() if match else ""
