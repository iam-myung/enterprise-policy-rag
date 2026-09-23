"""值对象（SPEC §4.1）。

domain 纯净：仅依赖标准库。
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DateRange:
    """生效日期区间（不可变值对象）。expires_at 不得早于 effective_at。"""

    effective_at: date | None
    expires_at: date | None

    def __post_init__(self) -> None:
        if (
            self.effective_at is not None
            and self.expires_at is not None
            and self.expires_at < self.effective_at
        ):
            raise ValueError("expires_at 不得早于 effective_at")
