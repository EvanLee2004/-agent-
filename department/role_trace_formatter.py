"""角色协作轨迹格式化器。"""

from department.role_trace import RoleTrace


class RoleTraceFormatter:
    """把角色轨迹渲染为 CLI 可读文本。"""

    def format(self, role_traces: list[RoleTrace]) -> str:
        """格式化角色轨迹。

        Args:
            role_traces: 当前回合角色轨迹列表。

        Returns:
            适合 CLI 打印的多行文本；没有轨迹时返回空字符串。
        """
        if not role_traces:
            return ""
        lines = ["协作过程："]
        for trace in role_traces:
            indent = "  " * trace.depth
            requester_text = f"（来自 {trace.requested_by}）" if trace.requested_by else ""
            lines.append(f"{indent}[{trace.display_name}] {requester_text}".rstrip())
            lines.append(f"{indent}目标：{trace.goal}")
            lines.append(f"{indent}思考摘要：{trace.thinking_summary}")
        return "\n".join(lines)
