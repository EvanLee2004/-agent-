"""文件配置仓储实现。"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from configuration.configuration_repository import ConfigurationRepository


load_dotenv()

CONFIG_FILE = Path("config.json")
ENV_FILE = Path(".env")
API_KEY_NAME = "LLM_API_KEY"


def _build_api_key_line(api_key: str) -> str:
    """构造 `.env` 中的 API Key 行。"""
    return f"{API_KEY_NAME}={api_key}"


def _upsert_api_key_lines(existing_lines: list[str], api_key_line: str) -> list[str]:
    """在 `.env` 内容中更新或追加 API Key。"""
    normalized_lines = []
    has_api_key = False
    for line in existing_lines:
        if line.startswith(f"{API_KEY_NAME}="):
            normalized_lines.append(api_key_line)
            has_api_key = True
            continue
        normalized_lines.append(line)
    if not has_api_key:
        normalized_lines.append(api_key_line)
    return normalized_lines


class FileConfigurationRepository(ConfigurationRepository):
    """基于文件系统的配置仓储实现。"""

    def load_config_data(self) -> Optional[dict]:
        """读取配置文件。

        Returns:
            配置字典；文件不存在或格式错误时返回 `None`。
        """
        if not CONFIG_FILE.exists():
            return None

        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def save_config_data(self, config_data: dict) -> None:
        """保存配置文件。

        Args:
            config_data: 需要持久化的配置字典。
        """
        CONFIG_FILE.write_text(
            json.dumps(config_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_api_key(self) -> str:
        """读取 API 密钥。

        Returns:
            `.env` 中保存的 API 密钥；不存在时返回空字符串。
        """
        return os.getenv(API_KEY_NAME, "").strip()

    def save_api_key(self, api_key: str) -> None:
        """保存 API 密钥。

        Args:
            api_key: 需要写入的 API 密钥。
        """
        if not ENV_FILE.exists():
            ENV_FILE.write_text(_build_api_key_line(api_key) + "\n", encoding="utf-8")
            return
        normalized_lines = _upsert_api_key_lines(
            ENV_FILE.read_text(encoding="utf-8").splitlines(),
            _build_api_key_line(api_key),
        )
        ENV_FILE.write_text("\n".join(normalized_lines) + "\n", encoding="utf-8")
