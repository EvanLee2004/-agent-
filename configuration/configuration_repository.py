"""配置仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional


class ConfigurationRepository(ABC):
    """配置仓储接口。"""

    @abstractmethod
    def load_config_data(self) -> Optional[dict]:
        """读取配置数据。

        Returns:
            配置字典；不存在时返回 `None`。
        """
        raise NotImplementedError

    @abstractmethod
    def save_config_data(self, config_data: dict) -> None:
        """保存配置数据。

        Args:
            config_data: 需要写入的配置字典。
        """
        raise NotImplementedError

    @abstractmethod
    def load_api_key(self) -> str:
        """读取 API 密钥。

        Returns:
            已保存的 API 密钥；不存在时返回空字符串。
        """
        raise NotImplementedError

    @abstractmethod
    def save_api_key(self, api_key: str) -> None:
        """保存 API 密钥。

        Args:
            api_key: 需要写入的 API 密钥。
        """
        raise NotImplementedError
