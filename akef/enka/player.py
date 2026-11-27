from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class Badge:
    name: str
    icon: str
    level: int = 0
    plated: bool = False
    slot: int = 0


@dataclass
class Rostered:
    name: str
    rarity: int
    element: str
    element_icon: str
    portrait: str
    level: int
    potential: int
    promotion: int | None = None
    profession: str = ""
    weapon_icon: str = ""
    weapon_rarity: int = 0
    id: str = ""


@dataclass
class Player:
    name: str
    uid: str
    level: int = 0
    world_level: int = 0
    region: str = ""
    avatar: str = ""
    namecard: str = ""
    signature: str = ""
    mission: str = ""
    created: datetime | None = None
    operators_owned: int = 0
    weapons_owned: int = 0
    files: int = 0
    medals: list[Badge] = field(default_factory=list)
    regions: list[tuple[str, int]] = field(default_factory=list)
    roster: list[Rostered] = field(default_factory=list)
    source: str = ""

    @property
    def days(self) -> int:
        if self.created is None:
            return 0
        return (datetime.now(timezone.utc) - self.created).days + 1

    def urls(self) -> list[str]:
        out = [self.avatar, self.namecard] + [m.icon for m in self.medals]
        for op in self.roster:
            out += [op.portrait, op.element_icon]
        return [u for u in out if u]
