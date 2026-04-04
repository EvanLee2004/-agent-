"""文件配置仓储测试。"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from configuration.file_configuration_repository import FileConfigurationRepository


class FileConfigurationRepositoryTest(unittest.TestCase):
    """验证真实文件仓储在 `.env` 读写边界上的行为。"""

    def test_load_env_value_reads_from_env_file_when_process_env_missing(self):
        """验证仓储会回退到 `.env` 文件，而不是只依赖进程环境变量。

        这个场景对应用户在同一进程中刚写完 `.env`、随后立即重新装配运行时。若仓储层
        只看 `os.environ`，那就会错误地认为密钥仍然不存在，导致配置服务无法启动。
        """
        repository = FileConfigurationRepository()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            env_file = temporary_root / ".env"
            env_file.write_text("MINIMAX_API_KEY=file-only-key\n", encoding="utf-8")
            original_cwd = Path.cwd()
            try:
                os.chdir(temporary_root)
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(
                        repository.load_env_value("MINIMAX_API_KEY"),
                        "file-only-key",
                    )
            finally:
                os.chdir(original_cwd)

    def test_save_env_value_updates_existing_variable_without_clobbering_others(self):
        """验证保存环境变量时只更新目标键，不破坏其他配置项。"""
        repository = FileConfigurationRepository()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            env_file = temporary_root / ".env"
            env_file.write_text(
                "MINIMAX_API_KEY=old-key\nOPENAI_API_KEY=openai-key\n",
                encoding="utf-8",
            )
            original_cwd = Path.cwd()
            try:
                os.chdir(temporary_root)
                repository.save_env_value("MINIMAX_API_KEY", "new-key")
                self.assertEqual(
                    env_file.read_text(encoding="utf-8"),
                    "MINIMAX_API_KEY=new-key\nOPENAI_API_KEY=openai-key\n",
                )
            finally:
                os.chdir(original_cwd)
