"""会计期间模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountingPeriod:
    """描述一个会计期间。

    Attributes:
        period_name: 期间标识，格式为 YYYYMM。
        start_date: 期间开始日期，格式为 YYYY-MM-DD。
        end_date: 期间结束日期，格式为 YYYY-MM-DD。
        status: 期间状态，当前只允许 open 或 closed。
        closed_at: 结账时间；未结账期间为空。
    """

    period_name: str
    start_date: str
    end_date: str
    status: str
    closed_at: str | None = None
