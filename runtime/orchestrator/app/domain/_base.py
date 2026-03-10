"""领域模型公共能力。"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


def utc_now() -> datetime:
    """返回带时区的 UTC 当前时间。"""

    return datetime.now(timezone.utc)


def ensure_utc_datetime(value: datetime | None) -> datetime | None:
    """确保时间值带有 UTC 时区。

    `SQLite` 在读取 `datetime` 时可能返回 naive 时间，
    这里统一把它归一化成 UTC aware 时间，避免状态对象内部比较时报错。
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


class DomainModel(BaseModel):
    """所有领域模型的最小公共基类。"""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=False,
    )
