"""架构约束测试。"""

import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIRECTORIES = [
    PROJECT_ROOT / "app",
    PROJECT_ROOT / "conversation",
    PROJECT_ROOT / "runtime",
    PROJECT_ROOT / "accounting",
    PROJECT_ROOT / "audit",
    PROJECT_ROOT / "tax",
    PROJECT_ROOT / "rules",
    PROJECT_ROOT / "configuration",
    PROJECT_ROOT / "department",
    PROJECT_ROOT / "cashier",
]
REMOVED_PATHS = [
    PROJECT_ROOT / "agents",
    PROJECT_ROOT / "services",
    PROJECT_ROOT / "infrastructure",
    PROJECT_ROOT / "tools",
    PROJECT_ROOT / "domain",
    PROJECT_ROOT / "providers",
    PROJECT_ROOT / "bootstrap.py",
    PROJECT_ROOT / "skills",
    PROJECT_ROOT / "llm",
    PROJECT_ROOT / "conversation" / "prompt_context_service.py",
    PROJECT_ROOT / "conversation" / "tool_loop_request.py",
    PROJECT_ROOT / "conversation" / "tool_loop_result.py",
    PROJECT_ROOT / "conversation" / "tool_loop_service.py",
    PROJECT_ROOT / "conversation" / "tool_router_catalog.py",
    PROJECT_ROOT / "conversation" / "tool_definition.py",
    PROJECT_ROOT / "conversation" / "file_prompt_skill_repository.py",
    PROJECT_ROOT / "conversation" / "prompt_skill_repository.py",
    PROJECT_ROOT / "conversation" / "finance_tool_context.py",
    PROJECT_ROOT / "conversation" / "finance_tool_context_registry.py",
    PROJECT_ROOT / ".agent_assets" / "skills" / "docx",
    PROJECT_ROOT / ".agent_assets" / "skills" / "pdf",
    PROJECT_ROOT / ".agent_assets" / "skills" / "pptx",
    PROJECT_ROOT / ".agent_assets" / "skills" / "xlsx",
    PROJECT_ROOT / "conversation" / "agent_runtime_repository.py",
    PROJECT_ROOT / "conversation" / "agent_runtime_request.py",
    PROJECT_ROOT / "conversation" / "agent_runtime_response.py",
    PROJECT_ROOT / "conversation" / "deerflow_agent_runtime_repository.py",
    PROJECT_ROOT / "conversation" / "deerflow_client_factory.py",
    PROJECT_ROOT / "conversation" / "deerflow_department_role_runtime_repository.py",
    PROJECT_ROOT / "conversation" / "deerflow_runtime_assets.py",
    PROJECT_ROOT / "conversation" / "deerflow_runtime_assets_service.py",
    PROJECT_ROOT / "conversation" / "deerflow_runtime_error.py",
    # 阶段 3：legacy 自写协作层已移除
    PROJECT_ROOT / "department" / "collaboration" / "collaborate_with_department_role_router.py",
    PROJECT_ROOT / "department" / "collaboration" / "collaborate_with_department_role_tool.py",
    PROJECT_ROOT / "department" / "collaboration" / "department_collaboration_command.py",
    PROJECT_ROOT / "department" / "collaboration" / "department_collaboration_service.py",
    PROJECT_ROOT / "department" / "department_workbench.py",
    PROJECT_ROOT / "department" / "department_workbench_repository.py",
    PROJECT_ROOT / "department" / "department_workbench_service.py",
    PROJECT_ROOT / "department" / "in_memory_department_workbench_repository.py",
    PROJECT_ROOT / "department" / "role_trace.py",
    PROJECT_ROOT / "department" / "role_trace_formatter.py",
    PROJECT_ROOT / "department" / "role_trace_summary_builder.py",
    # 自研记忆模块（已被 DeerFlow 原生记忆接管）
    PROJECT_ROOT / "memory" / "markdown_memory_store_repository.py",
    PROJECT_ROOT / "memory" / "memory_chunk.py",
    PROJECT_ROOT / "memory" / "memory_context_query.py",
    PROJECT_ROOT / "memory" / "memory_decision.py",
    PROJECT_ROOT / "memory" / "memory_error.py",
    PROJECT_ROOT / "memory" / "memory_index_repository.py",
    PROJECT_ROOT / "memory" / "memory_record.py",
    PROJECT_ROOT / "memory" / "memory_scope.py",
    PROJECT_ROOT / "memory" / "memory_search_result.py",
    PROJECT_ROOT / "memory" / "memory_service.py",
    PROJECT_ROOT / "memory" / "memory_store_repository.py",
    PROJECT_ROOT / "memory" / "search_memory_query.py",
    PROJECT_ROOT / "memory" / "search_memory_router.py",
    PROJECT_ROOT / "memory" / "search_memory_tool.py",
    PROJECT_ROOT / "memory" / "sqlite_memory_index_repository.py",
    PROJECT_ROOT / "memory" / "store_memory_command.py",
    PROJECT_ROOT / "memory" / "store_memory_router.py",
    PROJECT_ROOT / "memory" / "store_memory_tool.py",
    # 工具使用策略（依赖方已随记忆迁移一并移除）
    PROJECT_ROOT / "conversation" / "tool_use_policy.py",
]


class ArchitectureConstraintsTest(unittest.TestCase):
    """架构约束测试。"""

    def test_removed_legacy_paths_do_not_exist(self):
        """验证旧目录和旧入口已经删除。"""
        for path in REMOVED_PATHS:
            self.assertFalse(path.exists(), f"旧路径仍然存在: {path}")

    def test_no_utils_or_helpers_module_exists(self):
        """验证仓库中没有垃圾桶文件。"""
        forbidden_files = []
        for file_path in PROJECT_ROOT.rglob("*.py"):
            if ".venv" in file_path.parts:
                continue
            if file_path.name in {"utils.py", "helpers.py"}:
                forbidden_files.append(str(file_path))
        self.assertEqual(forbidden_files, [])

    def test_one_file_contains_at_most_one_top_level_class(self):
        """验证一个文件最多一个顶层类。"""
        violations = []
        for directory in TARGET_DIRECTORIES:
            for file_path in directory.rglob("*.py"):
                tree = ast.parse(file_path.read_text(encoding="utf-8"))
                top_level_classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
                if len(top_level_classes) > 1:
                    violations.append(str(file_path))
        self.assertEqual(violations, [])

    def test_readme_and_agents_no_legacy_fallback_claim(self):
        """验证文档不再声称 collaborate_with_department_role 仍保留作为 legacy fallback。

        阶段 3：legacy 工具已从 tool catalog 移除，文档应与实际实现一致。
        本测试防止"collaborate_with_department_role 仍保留"这类旧描述回退到 README/AGENTS。
        """
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        # README subagent_enabled 行不应声称 legacy fallback 仍保留
        for line in readme.splitlines():
            if "subagent_enabled" in line:
                self.assertNotIn("仍保留", line, "subagent_enabled 行不应声称 legacy fallback 仍保留")
                self.assertNotIn("legacy fallback", line.lower())

        # README 和 AGENTS 工具列表中均不应声称 collaborate_with_department_role 仍使用
        for doc_name, doc_content in [("README.md", readme), ("AGENTS.md", agents)]:
            # 允许出现在"阶段 3 已移除"的描述中，但不允许出现在"仍保留"/"legacy fallback"语境
            if "collaborate_with_department_role" in doc_content:
                self.assertNotIn(
                    "仍保留",
                    doc_content,
                    f"{doc_name} 不应声称 collaborate_with_department_role 仍保留",
                )
