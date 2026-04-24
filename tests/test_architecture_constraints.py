"""架构约束测试。"""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ArchitectureConstraintTest(unittest.TestCase):
    """验证项目已经收敛为 crewAI 会计部门。"""

    def test_removed_legacy_directories_do_not_exist(self):
        """旧扩展能力和旧运行时目录不应继续存在。"""
        removed_paths = [
            "cash" + "ier",
            "t" + "ax",
            "ru" + "les",
            "vendor",
            "department/collaboration",
            "department/subagent",
            "runtime/" + "deer" + "flow",
        ]

        for relative_path in removed_paths:
            with self.subTest(relative_path=relative_path):
                self.assertFalse((PROJECT_ROOT / relative_path).exists())

    def test_conversation_layer_does_not_import_runtime(self):
        """conversation 层不能依赖运行时适配层。"""
        for path in (PROJECT_ROOT / "conversation").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("runtime.crewai", source)
            self.assertNotIn("runtime." + "deer" + "flow", source)

    def test_crewai_runtime_is_the_only_runtime_adapter(self):
        """runtime 目录下只保留 crewAI 适配层。"""
        runtime_children = {
            path.name for path in (PROJECT_ROOT / "runtime").iterdir() if path.is_dir()
            and not path.name.startswith("__")
        }
        self.assertEqual(runtime_children, {"crewai"})

    def test_current_public_api_module_exists(self):
        """API 入口应使用会计部门命名。"""
        self.assertTrue((PROJECT_ROOT / "api" / "accounting_app.py").exists())
        self.assertFalse((PROJECT_ROOT / "api" / ("deer" + "flow_app.py")).exists())


if __name__ == "__main__":
    unittest.main()
