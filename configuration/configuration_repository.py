"""配置仓储接口。"""

from abc import ABC, abstractmethod
from typing import Optional


class ConfigurationRepository(ABC):
    """配置仓储接口。

    模型配置与环境变量读取都统一经过这一层，目的是把“配置文件格式如何落盘”和
    “环境变量如何读取/更新”从配置服务中剥离出去。这样后续无论切到别的持久化介质，
    配置服务都只需要继续处理业务校验，不需要知道底层文件细节。
    """

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
    def load_env_value(self, env_name: str) -> str:
        """读取指定环境变量值。

        Args:
            env_name: 环境变量名。

        Returns:
            当前环境变量值；不存在时返回空字符串。
        """
        raise NotImplementedError

    @abstractmethod
    def save_env_value(self, env_name: str, env_value: str) -> None:
        """保存指定环境变量值。

        Args:
            env_name: 环境变量名。
            env_value: 需要写入的环境变量值。
        """
        raise NotImplementedError
