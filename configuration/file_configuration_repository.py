"""文件配置仓储实现。"""

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values
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


def _read_env_value_from_file(env_name: str) -> str:
    """从 `.env` 文件中读取环境变量值。

    这里显式在读取阶段再次解析 `.env`，不是重复造 `python-dotenv` 的轮子，而是为了解决
    一个真实边界：同一进程里如果先调用 `save_env_value()` 更新了 `.env`，仅依赖模块导入
    时那一次 `load_dotenv()` 并不能保证 `os.environ` 立刻反映最新值。把文件读取补在
    仓储层，能够让“保存后再立即读取”的行为保持稳定，而不用把刷新环境变量的职责泄漏到
    配置服务或 CLI。
    """
    if not ENV_FILE.exists():
        return ""
    env_values = dotenv_values(ENV_FILE)
    env_value = env_values.get(env_name)
    return str(env_value).strip() if env_value else ""


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
        environment_value = os.getenv(env_name, "").strip()
        if environment_value:
            return environment_value
        return _read_env_value_from_file(env_name)

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
