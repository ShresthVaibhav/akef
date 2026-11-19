from __future__ import annotations

from pydantic import AliasChoices, Field, RootModel

from akef.models.base import Model, Tag, Timestamp


class Reward(Model):
    id: str
    name: str = ""
    count: int = 0
    icon: str = ""

    @property
    def display_name(self) -> str:
        # some names come as "Full Name|Short", keep the full one
        return self.name.split("|")[0]


class Day(Model):
    award_id: str
    available: bool = False
    done: bool = False


class Attendance(Model):
    calendar: list[Day] = []
    first: list[Day] = []
    resource_info_map: dict[str, Reward] = {}
    has_today: bool = False
    current_ts: Timestamp = None

    @property
    def claimed(self) -> int:
        return sum(1 for d in self.calendar if d.done)

    @property
    def today(self) -> Day | None:
        return next((d for d in self.calendar if d.available and not d.done), None)

    def reward(self, day: Day) -> Reward | None:
        return self.resource_info_map.get(day.award_id)


class Award(Model):
    id: str
    type: int = 0


class CheckIn(Model):
    award_ids: list[Award] = []
    tomorrow_award_ids: list[Award] = []
    resource_info_map: dict[str, Reward] = {}

    @property
    def rewards(self) -> list[Reward]:
        return [self.resource_info_map[a.id] for a in self.award_ids if a.id in self.resource_info_map]

    @property
    def tomorrow(self) -> list[Reward]:
        return [self.resource_info_map[a.id] for a in self.tomorrow_award_ids if a.id in self.resource_info_map]


class BannerItem(Model):
    id: str
    name: str = ""
    pic: str = ""
    rarity: str = ""
    pc_link: str = ""
    dot_type: str = ""

    @property
    def stars(self) -> int:
        tail = self.rarity.rsplit("_", 1)[-1]
        return int(tail) if tail.isdigit() else 0

    @property
    def featured(self) -> bool:
        return self.dot_type == "label_type_up"


class Banner(Model):
    id: str
    name: str = ""
    sort_id: int = 0
    items: list[BannerItem] = Field([], validation_alias=AliasChoices("chars", "weapons", "items"))
    start_at_ts: Timestamp = None
    end_at_ts: Timestamp = None
    pool_start_at_ts: Timestamp = None
    pool_end_at_ts: Timestamp = None
    europe_pool_start_at_ts: Timestamp = None
    europe_pool_end_at_ts: Timestamp = None

    def ends_at(self, server_type: str = "as"):
        # eu servers close a bit earlier than the rest
        if server_type == "eu" and self.europe_pool_end_at_ts:
            return self.europe_pool_end_at_ts
        return self.pool_end_at_ts or self.end_at_ts


class Enums(RootModel[dict[str, list[Tag]]]):
    def __getitem__(self, group: str) -> list[Tag]:
        return self.root.get(group, [])

    def groups(self) -> list[str]:
        return list(self.root)

    def label(self, key: str) -> str | None:
        for tags in self.root.values():
            for tag in tags:
                if tag.key == key:
                    return tag.value
        return None
