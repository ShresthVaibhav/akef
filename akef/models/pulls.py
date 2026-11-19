from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from pydantic import AliasChoices, BeforeValidator, ConfigDict, Field

from akef.models.base import Model

OPERATOR_BANNERS = ("special", "standard", "rerun", "beginner", "joint")
# limited operator banners share one 80 pity, the 120 for the featured one is per banner
LIMITED = ("special", "rerun", "joint")


def _millis(value):
    if isinstance(value, datetime) or value in (None, "", "0"):
        return value or None
    if isinstance(value, str) and not value.isdigit():
        return value
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


class Pull(Model):
    model_config = ConfigDict(extra="ignore")

    kind: str = "draw"
    banner: str = ""
    pool_id: str = ""
    pool_name: str = ""
    name: str = Field("", validation_alias=AliasChoices("charName", "weaponName", "nameText", "name"))
    item_id: str = Field("", validation_alias=AliasChoices("charId", "weaponId", "itemId", "item_id"))
    rarity: int = 0
    is_free: bool = False
    is_new: bool = False
    pulled_at: Annotated[datetime | None, BeforeValidator(_millis)] = Field(
        None, validation_alias=AliasChoices("gachaTs", "pulledAt", "pulled_at")
    )
    seq_id: int = 0


def since_last(pulls: list[Pull], rarity: int = 6) -> int:
    count = 0
    for pull in reversed(pulls):
        if pull.rarity >= rarity:
            break
        # urgent recruitment pulls are free and don't move pity
        if not pull.is_free:
            count += 1
    return count


class Pity(Model):
    name: str
    since_six: int
    hard: int
    banner: str = ""
    banner_pulls: int = 0
    featured_at: int = 0

    @property
    def left(self) -> int:
        return max(0, self.hard - self.since_six)


CSV_FIELDS = ("uid", "group", "kind", "banner", "pool_id", "pool_name", "name", "item_id", "rarity", "is_free", "is_new",
              "pulled_at", "seq_id")


class Pulls(Model):
    uid: str = ""
    operators: list[Pull] = []
    weapons: list[Pull] = []
    gifts: list[Pull] = []

    def to_json(self, indent: int | None = 2) -> str:
        return self.model_dump_json(indent=indent)

    def to_csv(self) -> str:
        out = io.StringIO()
        writer = csv.DictWriter(out, CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for group in ("operators", "weapons", "gifts"):
            for pull in getattr(self, group):
                row = pull.model_dump(include=set(CSV_FIELDS))
                row["pulled_at"] = pull.pulled_at.isoformat() if pull.pulled_at else ""
                row["is_free"], row["is_new"] = str(pull.is_free).lower(), str(pull.is_new).lower()
                writer.writerow(dict(row, uid=self.uid, group=group))
        return out.getvalue()

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        text = self.to_csv() if path.suffix.lower() == ".csv" else self.to_json()
        path.write_text(text, encoding="utf-8", newline="")
        return path

    @classmethod
    def load(cls, path: str | Path) -> Pulls:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() != ".csv":
            return cls.model_validate_json(text)
        pulls = cls()
        for row in csv.DictReader(io.StringIO(text)):
            pulls.uid = row.pop("uid") or pulls.uid
            getattr(pulls, row.pop("group")).append(Pull.model_validate(row))
        return pulls

    def banner(self, kind: str) -> list[Pull]:
        return [p for p in self.operators if p.banner == kind]

    def weapon_banner(self, pool_id: str) -> list[Pull]:
        return [p for p in self.weapons if p.pool_id == pool_id]

    @property
    def weapon_pools(self) -> list[str]:
        return list(dict.fromkeys(p.pool_id for p in self.weapons))

    @property
    def last_seq(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.operators:
            out[p.banner] = max(out.get(p.banner, 0), p.seq_id)
        for p in self.weapons:
            out[p.pool_id] = max(out.get(p.pool_id, 0), p.seq_id)
        return out

    def pity(self) -> list[Pity]:
        out = []
        limited = [p for p in self.operators if p.banner in LIMITED]
        if limited:
            current = limited[-1].pool_id
            paid = [p for p in limited if p.pool_id == current and not p.is_free]
            out.append(Pity(name="Limited operators", since_six=since_last(limited), hard=80,
                            banner=limited[-1].pool_name, banner_pulls=len(paid), featured_at=120))
        standard = self.banner("standard")
        if standard:
            out.append(Pity(name="Standard", since_six=since_last(standard), hard=80, banner=standard[-1].pool_name,
                            banner_pulls=sum(not p.is_free for p in standard), featured_at=300))
        beginner = self.banner("beginner")
        if beginner and not any(p.rarity == 6 for p in beginner):
            out.append(Pity(name="Beginner", since_six=since_last(beginner), hard=50))
        for pool in reversed(self.weapon_pools):
            pulls = self.weapon_banner(pool)
            out.append(Pity(name="Weapons", since_six=since_last(pulls), hard=40, banner=pulls[-1].pool_name,
                            banner_pulls=sum(not p.is_free for p in pulls), featured_at=80))
        return out
