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


def _build_env_line(env_name: str, env_value: str) -> str:
    """构造 `.env` 文件中的单行环境变量内容。"""
    return f"{env_name}={env_value}"


def _upsert_env_lines(
    existing_lines: list[str],
    env_name: str,
    env_value: str,
) -> list[str]:
    """在 `.env` 文本中更新或追加指定环境变量。

    这里显式按变量名做 upsert，而不是继续保留“只会写 LLM_API_KEY”的特殊逻辑，
    是因为多模型配置完成后，不同 provider 往往对应不同密钥环境变量。如果仓储层
    仍然只认识一个固定变量名，配置层就不得不重新发明一套环境变量写入逻辑。
    """
    normalized_lines = []
    has_target_env = False
    expected_prefix = f"{env_name}="
    for line in existing_lines:
        if line.startswith(expected_prefix):
            normalized_lines.append(_build_env_line(env_name, env_value))
            has_target_env = True
            continue
        normalized_lines.append(line)
    if not has_target_env:
        normalized_lines.append(_build_env_line(env_name, env_value))
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

    def load_env_value(self, env_name: str) -> str:
        """读取环境变量值。

        Args:
            env_name: 环境变量名。

        Returns:
            当前环境变量值；不存在时返回空字符串。
        """
        return os.getenv(env_name, "").strip()

    def save_env_value(self, env_name: str, env_value: str) -> None:
        """保存环境变量值到 `.env` 文件。

        Args:
            env_name: 环境变量名。
            env_value: 需要写入的环境变量值。
        """
        if not ENV_FILE.exists():
            ENV_FILE.write_text(
                _build_env_line(env_name, env_value) + "\n",
                encoding="utf-8",
            )
            return
        normalized_lines = _upsert_env_lines(
            ENV_FILE.read_text(encoding="utf-8").splitlines(),
            env_name,
            env_value,
        )
        ENV_FILE.write_text("\n".join(normalized_lines) + "\n", encoding="utf-8")
