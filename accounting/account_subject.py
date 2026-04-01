"""会计科目模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountSubject:
    """会计科目。

    Attributes:
        code: 科目编码。
        name: 科目名称。
        category: 科目类别。
        normal_balance: 正常余额方向。
        description: 科目说明。
    """

    code: str
    name: str
    category: str
    normal_balance: str
    description: str = ""
