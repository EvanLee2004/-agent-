"""角色协作轨迹格式化器。"""

from department.workbench.role_trace import RoleTrace


TRACE_SUMMARY_MAX_CHARS = 120


def _compress_summary_text(text: str) -> str:
    """压缩思考摘要文本。

    CLI 需要向用户展示“角色是如何协作的”，但不应该把完整最终回复在 trace 区域
    再重复打印一遍。这里把多行文本折叠并截断，是为了保留协作透明度，同时控制
    终端噪音，避免让 trace 反过来破坏主回复可读性。
    """
    normalized_text = " ".join(text.split())
    if len(normalized_text) <= TRACE_SUMMARY_MAX_CHARS:
        return normalized_text
    return normalized_text[: TRACE_SUMMARY_MAX_CHARS - 1] + "…"


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
            lines.append(f"{indent}思考摘要：{_compress_summary_text(trace.thinking_summary)}")
        return "\n".join(lines)
