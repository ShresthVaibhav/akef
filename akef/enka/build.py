from __future__ import annotations

from dataclasses import dataclass, field

from akef.enka.stats import GearLine, Stats

ELEMENT = {"Physical": "Physical", "Fire": "Heat", "Pulse": "Electric", "Cryst": "Cryo", "Natural": "Nature"}
ELEMENT_ICON = "https://enka.network/ui/ef/attributeicon/{}DamageIncrease.png"
ESSENCE_BASE = "https://enka.network/ui/ef/itemicon/{}.png"
PROFESSION = {
    "ASSAULT": "Striker",
    "VANGUARD": "Vanguard",
    "GUARD": "Guard",
    "DEFENDER": "Defender",
    "SUPPORTER": "Supporter",
    "CASTER": "Caster",
}
WEAPON_TYPE = {"Sword": "Sword", "Wand": "Arts Unit", "Claymores": "Greatsword", "Lance": "Polearm", "Pistol": "Handcannon"}
SLOT = {"body": "Armor", "hand": "Gloves", "edc": "Kit"}
SKILL_TYPE = {
    "NormalAttack": "Basic Attack",
    "NormalSkill": "Battle Skill",
    "ComboSkill": "Combo Skill",
    "UltimateSkill": "Ultimate",
}
PROMOTION = {"charBreak20": 1, "charBreak40": 2, "charBreak60": 3, "charBreak70": 4}


def element_icon(element: str) -> str:
    raw = next((k for k, v in ELEMENT.items() if v == element or k == element), "")
    return ELEMENT_ICON.format(raw) if raw else ""


def essence_base(template_id: str) -> str:
    return ESSENCE_BASE.format(template_id) if template_id.startswith("item_gem_rarity_") else ""


@dataclass
class Owner:
    name: str
    uid: str
    level: int = 0
    world_level: int = 0
    region: str = ""


@dataclass
class Skill:
    name: str
    kind: str
    icon: str
    level: int


@dataclass
class Talent:
    name: str
    icon: str
    level: int = 0
    max_level: int = 1
    kind: str = "combat"
    locked_icon: str = ""
    value: str = ""

    @property
    def unlocked(self) -> bool:
        return self.level > 0

    @property
    def maxed(self) -> bool:
        return self.level >= self.max_level


@dataclass
class EssenceTerm:
    name: str
    points: int = 0


@dataclass
class Essence:
    name: str
    icon: str
    terms: list[EssenceTerm] = field(default_factory=list)
    badge: str = ""


@dataclass
class WeaponSkill:
    name: str
    level: int
    stat: str = ""
    value: str = ""


@dataclass
class Weapon:
    name: str
    rarity: int
    icon: str
    level: int
    refine: int
    breakthrough: int
    essence: Essence | None = None
    skills: list[WeaponSkill] = field(default_factory=list)


@dataclass
class Gear:
    slot: str
    icon: str
    rarity: int
    set_name: str = ""
    defense: int = 0
    lines: list[GearLine] = field(default_factory=list)


@dataclass
class Tactical:
    name: str
    icon: str


@dataclass
class Build:
    id: str
    name: str
    rarity: int
    element: str
    profession: str
    weapon_type: str
    level: int
    promotion: int
    potential: int
    art: str
    owner: Owner
    skills: list[Skill] = field(default_factory=list)
    talents: list[Talent] = field(default_factory=list)
    weapon: Weapon | None = None
    gear: list[Gear] = field(default_factory=list)
    tactical: Tactical | None = None
    stats: Stats | None = None
    source: str = ""
    element_icon: str = ""

    @property
    def talent_progress(self) -> tuple[int, int]:
        return sum(t.level for t in self.talents), sum(t.max_level for t in self.talents)

    @property
    def gear_set(self) -> tuple[str, int]:
        counts: dict[str, int] = {}
        for piece in self.gear:
            if piece.set_name:
                counts[piece.set_name] = counts.get(piece.set_name, 0) + 1
        if not counts:
            return "", 0
        best = max(counts, key=counts.get)
        return best, counts[best]

    def urls(self) -> list[str]:
        out = [self.art, self.element_icon] + [s.icon for s in self.skills]
        out += [t.icon for t in self.talents] + [t.locked_icon for t in self.talents]
        if self.weapon:
            out.append(self.weapon.icon)
            if self.weapon.essence:
                out += [self.weapon.essence.icon, self.weapon.essence.badge]
        out += [g.icon for g in self.gear]
        if self.tactical:
            out.append(self.tactical.icon)
        return [u for u in out if u]


def amount(value: float) -> str:
    return f"+{value:g}"
