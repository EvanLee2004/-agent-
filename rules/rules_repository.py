"""规则仓储接口。"""

from abc import ABC, abstractmethod


class RulesRepository(ABC):
    """规则仓储接口。"""

    @abstractmethod
    def load_rules_text(self) -> str:
        """读取规则文本。

        Returns:
            规则文本。
        """
        raise NotImplementedError
