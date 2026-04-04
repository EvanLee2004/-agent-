"""财务子代理专业模式 Prompt 模板定义。"""

from dataclasses import dataclass

from department.subagent.fiscal_role_mode import FiscalRoleMode


@dataclass(frozen=True)
class FiscalRolePrompt:
    """一个专业模式的 prompt 内容。"""

    mode: FiscalRoleMode
    identity: str
    available_tools: list[str]
    authority_boundaries: list[str]
    evidence_requirements: list[str]
    output_format: str
