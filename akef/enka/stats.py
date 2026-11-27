import math
from collections import defaultdict
from dataclasses import dataclass, field

from akef.errors import MissingGameData
from akef.enka.gamedata import GameData, slot_of

STR, AGI, INT, WILL = 39, 40, 41, 42
HP, ATK, DEF = 1, 2, 3
MAIN, SUB = 10000, 10001
ETHER_DMG = 55

PART = {
    "BaseAddition": "base",
    "BaseMultiplier": "ratio",
    "BaseFinalMultiplier": "delta",
    "BaseFinalAddition": "delta",
    "Addition": "delta",
}
ATTR_FIELD = {STR: "strength", AGI: "agility", INT: "intellect", WILL: "will"}
LABEL = {
    1: "HP", 2: "ATK", 3: "DEF", 9: "Crit Rate", 10: "Crit DMG", 17: "Basic Attack DMG", 28: "Ultimate DMG",
    29: "Treatment Bonus", 32: "Battle Skill DMG", 33: "Combo Skill DMG", 39: "Strength", 40: "Agility",
    41: "Intellect", 42: "Will", 44: "Ult Gain", 50: "Physical DMG", 51: "Heat DMG", 52: "Electric DMG",
    53: "Cryo DMG", 54: "Nature DMG", 61: "DMG vs. Staggered", 87: "Arts Intensity",
}
GROUP_LABEL = {
    frozenset({52, 53}): "Cryo & Electric DMG",
    frozenset({51, 54}): "Heat & Nature DMG",
    frozenset({51, 52, 53, 54}): "Arts DMG",
    frozenset({28, 32, 33}): "All Skill DMG",
    frozenset({4, 5, 6, 7, 48, 60}): "DMG Reduction",
}
FLAT = {HP, ATK, DEF, STR, AGI, INT, WILL, 87, MAIN, SUB}


@dataclass
class Stats:
    strength: int = 0
    agility: int = 0
    intellect: int = 0
    will: int = 0
    hp: int = 0
    atk: int = 0
    defense: int = 0
    crit_rate: float = 0
    crit_dmg: float = 0
    arts_intensity: float = 0
    treatment_bonus: float = 0
    treatment_received: float = 0
    ult_gain: float = 0
    stagger_dmg: float = 0
    physical_dmg: float = 0
    heat_dmg: float = 0
    electric_dmg: float = 0
    cryo_dmg: float = 0
    nature_dmg: float = 0
    basic_attack_dmg: float = 0
    battle_skill_dmg: float = 0
    combo_skill_dmg: float = 0
    ultimate_dmg: float = 0
    main_attribute: str = ""
    sub_attribute: str = ""

    def percent(self, name: str) -> str:
        # half up to one decimal like the game. game keeps fewer digits so 216.2499986 still shows 216.3
        value = getattr(self, name) * 100
        return f"{math.floor(value * 10 + 0.5 + 1e-4) / 10:.1f}%"


@dataclass
class GearLine:
    name: str
    value: float
    percent: bool
    level: int = 0
    max_level: int = 3

    @property
    def text(self) -> str:
        if self.percent:
            return f"+{(self.value + 1e-4) * 100:.1f}%"
        return f"+{math.floor(self.value):,}"


@dataclass
class GearStats:
    slot: str
    defense: int = 0
    lines: list[GearLine] = field(default_factory=list)


@dataclass
class Loadout:
    avatar: dict
    level: int = 1
    potential: int = 0
    attr_nodes: list[str] = field(default_factory=list)
    passive_nodes: list[str] = field(default_factory=list)
    weapon: dict | None = None
    weapon_level: int = 1
    weapon_skill_levels: list[int] = field(default_factory=list)
    gear: list[tuple[dict, dict[str, int]]] = field(default_factory=list)


class Sheet:
    def __init__(self, main: int, sub: int):
        self.main = main
        self.sub = sub
        self.parts: dict[tuple[int, str], float] = defaultdict(float)
        self.atk_total_ratio = 0.0

    def add(self, stat, value: float, formula: str = "BaseAddition") -> None:
        stat = int(stat)
        if stat == MAIN:
            stat = self.main
        elif stat == SUB:
            stat = self.sub
        self.parts[(stat, PART.get(formula, "base"))] += value

    def flat(self, stat: int) -> int:
        p = self.parts
        return math.floor(p[(stat, "base")] * (1 + p[(stat, "ratio")]) + p[(stat, "delta")])

    def sum(self, stat: int) -> float:
        return self.parts[(stat, "base")] + self.parts[(stat, "delta")]


def weapon_skill_levels(data: GameData, weapon: dict, refine: int, breakthrough: int, gem_terms=()) -> list[int]:
    none = [{"lowerBound": 0, "upperBound": 0}] * 3
    by_refine = data.refine_bounds.get(weapon["TalentTemplateId"], {}).get(str(refine)) or none
    by_break = data.break_bounds[weapon["BreakthroughTemplateId"]][str(breakthrough)]
    extra = {}
    for term_id, cost in gem_terms:
        term = data.gem_terms.get(str(term_id))
        if term:
            extra[term["TagId"]] = cost
    levels = []
    for i, skill_id in enumerate(weapon["SkillList"]):
        lower = by_refine[i]["lowerBound"] + by_break[i]["lowerBound"]
        upper = by_refine[i]["upperBound"] + by_break[i]["upperBound"]
        tag = data.skills[str(skill_id)]["TagId"]
        levels.append(min(lower + extra.get(tag, 0), upper))
    return levels


def skill_effect(data: GameData, skill_id, level: int, avatar: dict | None = None) -> tuple[str, str]:
    props = [(int(s), p) for s, p in data.skills[str(skill_id)]["PropMap"].items() if int(s) != ETHER_DMG]
    if not props or level < 1:
        return "", ""
    stat, prop = props[0]
    value = prop["Values"][min(level, len(prop["Values"])) - 1]
    if stat in (MAIN, SUB):
        attr = avatar and avatar["MainAttrId" if stat == MAIN else "SubAttrId"]
        name = LABEL.get(attr, "Main Attribute" if stat == MAIN else "Secondary Attribute")
    else:
        name = LABEL.get(stat, "")
    if prop["Formula"] == "BaseMultiplier" or stat not in FLAT:
        return name, f"+{(value + 1e-4) * 100:.1f}%"
    return name, f"+{math.floor(value):,}"


def gear_slots(item: dict, enhance: dict[str, int]):
    # an affix spread over several stat ids shares one enhance slot, so reuse the slot while values repeat
    previous, key = None, 1
    for index, mod in enumerate(item["AttrModifiers"]):
        level = enhance.get(str(key))
        same = level is not None and level < len(mod["Values"]) and mod["Values"][level] == previous
        key = key if same else min(index, 3)
        value = mod["Values"][enhance.get(str(key), 0) or 0]
        previous = value
        yield key, mod, value


def gear_stats(loadout: Loadout) -> list[GearStats]:
    out = []
    for item, enhance in loadout.gear:
        groups: dict[int, list] = {}
        defense = 0.0
        for key, mod, value in gear_slots(item, enhance):
            if key == 0:
                defense += value
            else:
                groups.setdefault(key, []).append((mod, value))
        lines = []
        for key in sorted(groups):
            mods = groups[key]
            mod, value = mods[0]
            stat, formula = mod["AttrType"], mod["Formula"]
            ids = frozenset(m["AttrType"] for m, _ in mods)
            if stat in (MAIN, SUB):
                attr = loadout.avatar["MainAttrId"] if stat == MAIN else loadout.avatar["SubAttrId"]
                name = LABEL[attr]
            else:
                name = GROUP_LABEL.get(ids) or LABEL.get(stat, str(stat))
            if formula == "BaseFinalMultiplier":
                value = 1 - value
            percent = formula == "BaseMultiplier" or (stat not in FLAT and stat not in (MAIN, SUB))
            lines.append(GearLine(name, value, percent, enhance.get(str(key), 0) or 0, len(mod["Values"]) - 1))
        out.append(GearStats(slot_of(item["Icon"]), math.floor(defense), lines))
    return out


def _corrections(sheet: Sheet, loadout: Loadout) -> None:
    latest = set(loadout.passive_nodes)
    sid = loadout.avatar["StrId"]
    will, intellect = sheet.flat(WILL), sheet.flat(INT)
    if sid == "chr_0020_meurs":
        if f"{sid}_passive_skill_0_1" in latest:
            sheet.add(DEF, math.floor(will / 10), "Addition")
        elif f"{sid}_passive_skill_0_2" in latest:
            sheet.add(DEF, math.floor(will / 10) * 1.2, "Addition")
    elif sid == "chr_0015_lifeng":
        if f"{sid}_passive_skill_0_1" in latest:
            sheet.atk_total_ratio += (intellect + will) * 0.001
        elif f"{sid}_passive_skill_0_2" in latest:
            sheet.atk_total_ratio += (intellect + will) * 0.0015


def calculate(data: GameData, loadout: Loadout) -> Stats:
    excel = loadout.avatar
    sheet = Sheet(excel["MainAttrId"], excel["SubAttrId"])
    level = max(loadout.level, 1)

    for stat, growth in excel["BaseAttributes"].items():
        sheet.add(stat, growth["BaseValue"] + growth["AddValue"] * (level - 1))
    sheet.add(HP, excel["BaseHpByLevel"][level - 1])
    sheet.add(ATK, excel["BaseAtkByLevel"][level - 1])
    sheet.add(44, 1)
    sheet.add(10, 0.5)

    for pot in excel["PotAttributes"]:
        if loadout.potential >= pot["Level"]:
            for stat, attr in pot["Attrs"].items():
                sheet.add(stat, attr["Value"], attr["Formula"])

    weapon = loadout.weapon
    if weapon:
        sheet.add(ATK, data.curves[weapon["LevelTemplateId"]][max(loadout.weapon_level, 1) - 1])
        for skill_id, level_ in zip(weapon["SkillList"], loadout.weapon_skill_levels):
            if level_ < 1:
                continue
            for stat, prop in data.skills[str(skill_id)]["PropMap"].items():
                if int(stat) == ETHER_DMG:
                    continue
                sheet.add(stat, prop["Values"][min(level_, len(prop["Values"])) - 1], prop["Formula"])

    suits: dict[str, int] = defaultdict(int)
    for item, enhance in loadout.gear:
        if item["SuitId"]:
            suits[item["SuitId"]] += 1
        for _, mod, value in gear_slots(item, enhance):
            sheet.add(mod["AttrType"], value, mod["Formula"])
    for suit, count in suits.items():
        if count >= 3:
            for stat, prop in data.skills[str(data.suits[suit]["SkillId"])]["PropMap"].items():
                sheet.add(stat, prop["Values"][0], prop["Formula"])

    unlocked = set(loadout.attr_nodes)
    for node, attrs in excel["AttributeNodes"].items():
        if node in unlocked:
            for stat, value in attrs.items():
                sheet.add(stat, value)

    sheet.add(HP, sheet.flat(STR) * 5)
    sheet.add(30, sheet.flat(WILL) * 0.001, "Addition")
    sheet.atk_total_ratio += sheet.flat(sheet.main) * 0.005 + sheet.flat(sheet.sub) * 0.002
    _corrections(sheet, loadout)

    p = sheet.parts
    atk = math.floor((p[(ATK, "base")] * (1 + p[(ATK, "ratio")]) + p[(ATK, "delta")]) * (1 + sheet.atk_total_ratio))
    return Stats(
        strength=sheet.flat(STR),
        agility=sheet.flat(AGI),
        intellect=sheet.flat(INT),
        will=sheet.flat(WILL),
        hp=sheet.flat(HP),
        atk=atk,
        defense=sheet.flat(DEF),
        crit_rate=sheet.sum(9),
        crit_dmg=sheet.sum(10),
        # the game drops the fraction instead of rounding
        arts_intensity=math.floor(sheet.sum(87) + 1e-6),
        treatment_bonus=sheet.sum(29),
        treatment_received=sheet.sum(30),
        ult_gain=sheet.sum(44),
        stagger_dmg=sheet.sum(61),
        physical_dmg=sheet.sum(50),
        heat_dmg=sheet.sum(51),
        electric_dmg=sheet.sum(52),
        cryo_dmg=sheet.sum(53),
        nature_dmg=sheet.sum(54),
        basic_attack_dmg=sheet.sum(17),
        battle_skill_dmg=sheet.sum(32),
        combo_skill_dmg=sheet.sum(33),
        ultimate_dmg=sheet.sum(28),
        main_attribute=ATTR_FIELD.get(sheet.main, ""),
        sub_attribute=ATTR_FIELD.get(sheet.sub, ""),
    )


def require(found, kind: str, name):
    if found is None:
        raise MissingGameData(kind, name)
    return found
