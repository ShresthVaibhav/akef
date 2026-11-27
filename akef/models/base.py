from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict
from pydantic.alias_generators import to_camel


def _timestamp(value):
    if isinstance(value, datetime) or value is None:
        return value
    # skport sends unix seconds as strings and "0" when there's nothing
    if str(value) in ("", "0"):
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


Timestamp = Annotated[datetime | None, BeforeValidator(_timestamp)]


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="allow")


class Tag(Model):
    key: str = ""
    value: str = ""

    def __str__(self) -> str:
        return self.value


class Progress(Model):
    count: int = 0
    total: int = 0

    @property
    def done(self) -> bool:
        return self.total > 0 and self.count >= self.total
