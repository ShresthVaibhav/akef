from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp

from akef.enka.build import (
    ELEMENT,
    PROFESSION,
    PROMOTION,
    SKILL_TYPE,
    SLOT,
    WEAPON_TYPE,
    Build,
    Essence,
    EssenceTerm,
    Gear,
    Owner,
    Skill,
    Talent,
    Weapon,
    WeaponSkill,
    amount,
    element_icon,
)
from akef.errors import NetworkError, PlayerNotFound, ShowcaseEmpty
from akef.models.card import tier_unlocked
from akef.enka.gamedata import GameData, slot_of
from akef.enka.player import Badge, Player, Rostered
from akef.enka.stats import Loadout, calculate, gear_stats, require, skill_effect, weapon_skill_levels

ENKA = "https://enka.network"
API = ENKA + "/api/ef/uid/{}/"
ATTR_ICON = {39: "Str", 40: "Agi", 41: "Wisd", 42: "Will"}
ATTR_NAME = {39: "Strength", 40: "Agility", 41: "Intellect", 42: "Will"}
SKILL_ORDER = ("dispNormalAttackSkill", "normalSkill", "comboSkill", "ultimateSkill")
SLOT_ORDER = {"body": 0, "hand": 1, "edc": 2}


@dataclass
class EnkaProfile:
    owner: Owner
    builds: list[Build] = field(default_factory=list)
    signature: str = ""
    ttl: int = 0
    raw: dict = field(default_factory=dict, repr=False)
    player: Player | None = None

    def build(self, name: str) -> Build | None:
        wanted = name.lower()
        return next((b for b in self.builds if b.name.lower() == wanted or b.id == name), None)


def asset(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    if not path.startswith("/"):
        path = "/ui/ef/" + path + ("" if path.endswith((".png", ".webp")) else ".png")
    return ENKA + path


def talent_icon(path: str) -> str:
    # enka's table says /ui/ef/icon_talent_x.png but the file is served from skillicon/
    if path.startswith("/ui/ef/icon_talent_"):
        path = path.replace("/ui/ef/", "/ui/ef/skillicon/", 1)
    return asset(path)


def item_icon(path: str) -> str:
    # weapon and essence art lives under itemicon/ on enka's cdn
    if "/itemicon/" not in path:
        path = path.replace("/ui/ef/", "/ui/ef/itemicon/", 1)
    return asset(path)


async def fetch_player(uid: int | str, *, session: aiohttp.ClientSession | None = None, timeout: float = 20) -> dict:
    own = session is None
    session = session or aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout), headers={"User-Agent": "akef"}
    )
    try:
        async with session.get(API.format(uid)) as resp:
            if resp.status in (400, 404):
                raise PlayerNotFound(f"Enka doesn't know UID {uid}")
            if resp.status == 424:
                raise NetworkError("Endfield's servers are under maintenance, try again later")
            if resp.status == 429:
                raise NetworkError("Enka is rate limiting us, slow down a little")
            if resp.status != 200:
                raise NetworkError(f"Enka returned http {resp.status}")
            return await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise NetworkError(f"couldn't reach Enka: {exc.__class__.__name__}") from exc
    finally:
        if own:
            await session.close()


def _skill_name(name: str) -> str:
    return re.sub(r"\s*\[[A-Z]\]$", "", name.split(":")[0]).strip()


async def _weapon(data: GameData, raw: dict, avatar: dict) -> tuple[Weapon, dict, list[int]]:
    key = str(raw["templateId"])
    excel = require(data.weapons.get(key), "weapon", key)
    tip = await data.tooltip("Weapons", key) or {}
    gem = raw.get("attachedGem") or {}
    terms = [(t["termNumId"], t["cost"]) for t in gem.get("terms") or []]
    levels = weapon_skill_levels(data, excel, raw.get("refineLv", 0), raw.get("breakthroughLv", 0), terms)

    essence = None
    if gem:
        skill_names = {}
        for skill_id, skill in (tip.get("SkillMap") or {}).items():
            skill_names[skill.get("TagId") or data.skills.get(skill_id, {}).get("TagId")] = _skill_name(skill["Name"])
        names, title, badge = [], "", ""
        for term_id, cost in terms:
            term = data.gem_terms.get(str(term_id), {})
            name = skill_names.get(term.get("TagId")) or term.get("TagId", "").replace("attr_", "").title()
            names.append(EssenceTerm(name, cost))
            if term.get("TermType") == 3:
                title, badge = name, term.get("TagIcon", "")
            badge = badge or term.get("TagIcon", "")
        icon = data.gem_items.get(str(gem.get("templateId")), {}).get("Icon", "")
        essence = Essence(title or "Essence", item_icon(icon) if icon else "", names, asset(badge) if badge else "")

    skills = []
    for skill_id, level in zip(excel["SkillList"], levels):
        name = ((tip.get("SkillMap") or {}).get(str(skill_id)) or {}).get("Name", "")
        stat, value = skill_effect(data, skill_id, level, avatar)
        skills.append(WeaponSkill(_skill_name(name) or stat, level, stat, value))

    weapon = Weapon(
        name=tip.get("Name") or data.name(excel["NameHash"]),
        rarity=excel["Rarity"],
        icon=item_icon(excel["Icon"]),
        level=raw.get("weaponLv", 1),
        refine=raw.get("refineLv", 0),
        breakthrough=raw.get("breakthroughLv", 0),
        essence=essence,
        skills=skills,
    )
    return weapon, excel, levels


async def _build(data: GameData, raw: dict, owner: Owner) -> Build:
    key = str(raw["templateId"])
    avatar = require(data.avatars.get(key), "operator", key)
    tip = await data.tooltip("Avatars", key) or {}
    sid = avatar["StrId"]
    talent = raw.get("talent") or {}
    attr_nodes = talent.get("attrNodes") or []
    latest = (talent.get("latestPassiveSkillNodes") or []) + (talent.get("latestFactorySkillNodes") or [])

    info = raw.get("skillInfo") or {}
    levels = {s["skillId"]: s.get("skillLevel", 0) for s in info.get("levelInfo") or []}
    skills = []
    for slot in SKILL_ORDER:
        skill_id = info.get(slot)
        if not skill_id:
            continue
        excel_skill = avatar["SkillInfoMap"].get(skill_id, {})
        tip_skill = (tip.get("SkillInfoMap") or {}).get(skill_id, {})
        kind = SKILL_TYPE.get(skill_id.rsplit("_", 1)[-1], "")
        skills.append(Skill(tip_skill.get("Name") or kind, kind, asset(excel_skill.get("Icon", "")), levels.get(skill_id, 0)))

    talents = []
    tip_nodes = tip.get("NodeSkillMap") or {}
    nodes = avatar["AttributeNodes"]
    if nodes:
        key = next(iter(next(iter(nodes.values()))))
        attr = int(key)
        # some operators raise two stats per node by the same amount, the first one stands for both
        total = sum((nodes.get(node) or {}).get(key, 0) for node in attr_nodes)
        talents.append(Talent(ATTR_NAME.get(attr, ""), asset(f"/ui/ef/attributeicon/{ATTR_ICON.get(attr, 'Str')}.png"),
                              sum(node in nodes for node in attr_nodes), len(nodes), "attribute", value=amount(total)))
    lines: dict[int, list[tuple[str, dict]]] = {}
    for node, info_ in avatar["NodeSkillMap"].items():
        lines.setdefault(info_["Index"], []).append((node, info_))
    for index in sorted(lines):
        tiers = sorted(lines[index], key=lambda kv: kv[1]["Level"])
        level = max((info_["Level"] for node, info_ in tiers if tier_unlocked(node, latest)), default=0)
        shown = tiers[max(level, 1) - 1]
        name = (tip_nodes.get(shown[0]) or {}).get("Name", shown[0])
        kind = "base" if shown[1].get("Type") == 5 else "combat"
        talents.append(Talent(name, talent_icon(shown[1]["Icon"]), level, len(tiers), kind))

    weapon = weapon_excel = None
    weapon_levels: list[int] = []
    if raw.get("weapon"):
        weapon, weapon_excel, weapon_levels = await _weapon(data, raw["weapon"], avatar)

    gear, loadout_gear = [], []
    for entry in raw.get("equip") or []:
        value = entry["value"]
        item = require(data.items.get(str(value["templateid"])), "gear", value["templateid"])
        enhance = {str(e["key"]): e["value"] for e in value.get("enhance") or []}
        loadout_gear.append((item, enhance))
    loadout_gear.sort(key=lambda pair: SLOT_ORDER.get(slot_of(pair[0]["Icon"]), 3))

    loadout = Loadout(
        avatar=avatar,
        level=raw.get("level", 1),
        potential=raw.get("potentialLevel", 0),
        attr_nodes=attr_nodes,
        passive_nodes=talent.get("latestPassiveSkillNodes") or [],
        weapon=weapon_excel,
        weapon_level=weapon.level if weapon else 1,
        weapon_skill_levels=weapon_levels,
        gear=loadout_gear,
    )
    for (item, _), stats in zip(loadout_gear, gear_stats(loadout)):
        set_name = ""
        if item["SuitId"]:
            suit_tip = await data.tooltip("Suits", item["SuitId"]) or {}
            set_name = suit_tip.get("Name") or data.name(data.suits.get(item["SuitId"], {}).get("NameHash"))
        gear.append(Gear(SLOT.get(stats.slot, stats.slot), asset(item["Icon"]), item["Rarity"], set_name, stats.defense,
                         stats.lines))

    return Build(
        id=sid,
        name=tip.get("Name") or data.name(avatar["NameHash"]),
        rarity=avatar["Rarity"],
        element=ELEMENT.get(avatar["Element"], avatar["Element"]),
        profession=PROFESSION.get(avatar["Profession"], avatar["Profession"].title()),
        weapon_type=WEAPON_TYPE.get(avatar["WeaponType"], avatar["WeaponType"]),
        level=raw.get("level", 1),
        promotion=PROMOTION.get(talent.get("latestBreakNode", ""), 0),
        potential=raw.get("potentialLevel", 0),
        art=asset(f"/ui/ef/splash/{raw.get('variantId') or sid}.webp"),
        owner=owner,
        skills=skills,
        talents=talents,
        weapon=weapon,
        gear=gear,
        stats=calculate(data, loadout),
        source="enka",
        element_icon=element_icon(avatar["Element"]),
    )


async def profile_from_enka(data: GameData, raw: dict) -> EnkaProfile:
    card = (raw.get("playerInfo") or {}).get("businessCard") or {}
    owner = Owner(
        name=card.get("name", "?"),
        uid=str(raw.get("uid") or card.get("platformRoleId", "")),
        level=card.get("adventureLevel", 0),
        world_level=card.get("worldLevel", 0),
        region=str(raw.get("region", "")).title(),
    )
    chars = (raw.get("playerInfo") or {}).get("charData") or []
    if not chars and not card.get("charList"):
        raise ShowcaseEmpty(f"{owner.name} has no operators in their showcase, or hid them")
    builds = [await _build(data, c, owner) for c in chars]
    player = await player_from_enka(data, raw, builds)
    return EnkaProfile(owner, builds, card.get("signature", ""), raw.get("ttl", 0), raw, player)


REGIONS = {"domain_1": "Valley IV", "domain_2": "Wuling"}


def _medal(data: GameData, medal_id, level: int, plated: bool, slot: int = 0) -> Badge | None:
    medal = data.medals.get(str(medal_id))
    if not medal:
        return None
    icons = medal.get("IconByLevel") or {}
    usable = sorted((int(k) for k in icons), reverse=True)
    pick = next((k for k in usable if k <= level), usable[-1] if usable else None)
    icon = icons[str(pick)] if pick else ""
    if icon and plated:
        icon = icon.replace(".png", "_plating.png")
    return Badge(data.name(medal.get("NameHash")), asset(icon) if icon else "", level, plated, slot)


async def player_from_enka(data: GameData, raw: dict, builds: list[Build]) -> Player:
    card = (raw.get("playerInfo") or {}).get("businessCard") or {}
    achieve = card.get("achievement") or {}
    info = {m["achieveNumId"]: m for m in achieve.get("infoList") or []}
    medals = []
    for slot in sorted(achieve.get("display") or [], key=lambda s: s["key"]):
        got = info.get(slot["value"], {})
        badge = _medal(data, slot["value"], got.get("level", 1), got.get("isPlated", False), slot["key"])
        if badge:
            medals.append(badge)

    by_id = {b.id: b for b in builds}
    roster = []
    for entry in card.get("charList") or []:
        found = data.avatar_by_str.get(entry["templateId"])
        if not found:
            continue
        key, avatar = found
        tip = await data.tooltip("Avatars", key) or {}
        build = by_id.get(entry["templateId"])
        weapon = build.weapon if build else None
        roster.append(Rostered(
            name=tip.get("Name") or data.name(avatar["NameHash"]),
            rarity=avatar["Rarity"],
            element=ELEMENT.get(avatar["Element"], avatar["Element"]),
            element_icon=element_icon(avatar["Element"]),
            portrait=build.art if build else asset(f"/ui/ef/splash/{entry['templateId']}.webp"),
            id=entry["templateId"],
            level=entry.get("level", 0),
            potential=entry.get("potentialLevel", 0),
            promotion=build.promotion if build else None,
            profession=PROFESSION.get(avatar["Profession"], avatar["Profession"].title()),
            weapon_icon=weapon.icon if weapon else "",
            weapon_rarity=weapon.rarity if weapon else 0,
        ))

    stats = card.get("statistic") or {}
    regions = [(REGIONS.get(d["domainId"], d["domainId"]), d.get("level", 0))
               for d in (card.get("domainDev") or {}).get("domains") or []]
    created = card.get("createTime")
    return Player(
        name=card.get("name", "?"),
        uid=str(raw.get("uid") or card.get("platformRoleId", "")),
        level=card.get("adventureLevel", 0),
        world_level=card.get("worldLevel", 0),
        region=str(raw.get("region", "")).title(),
        avatar=asset((data.pfps.get(str(card.get("userAvatarId"))) or {}).get("Icon", "")),
        namecard=asset((data.namecards.get(str(card.get("businessCardTopicId"))) or {}).get("Icon", "")),
        signature=card.get("signature", ""),
        created=datetime.fromtimestamp(created, tz=timezone.utc) if created else None,
        operators_owned=stats.get("charNum", 0),
        weapons_owned=stats.get("weaponNum", 0),
        files=stats.get("docNum", 0),
        medals=medals,
        regions=regions,
        roster=roster,
        source="enka",
    )
