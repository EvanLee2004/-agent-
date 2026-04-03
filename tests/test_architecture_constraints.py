"""架构约束测试。"""

import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIRECTORIES = [
    PROJECT_ROOT / "app",
    PROJECT_ROOT / "conversation",
    PROJECT_ROOT / "accounting",
    PROJECT_ROOT / "audit",
    PROJECT_ROOT / "tax",
    PROJECT_ROOT / "memory",
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
