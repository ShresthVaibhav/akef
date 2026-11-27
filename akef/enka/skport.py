import re

from akef.enka.build import (
    ELEMENT,
    PROFESSION,
    WEAPON_TYPE,
    Build,
    Essence,
    EssenceTerm,
    Gear,
    Owner,
    Skill,
    Tactical,
    Talent,
    Weapon,
    WeaponSkill,
    amount,
    element_icon,
    essence_base,
)
from akef.errors import MissingGameData
from akef.enka.gamedata import GameData
from akef.enka.player import Badge, Player, Rostered
from akef.enka.stats import DEF, MAIN, SUB, Loadout, calculate, gear_stats, skill_effect


GEAR_PROPS = {
    "equip_attr_str": (39,),
    "equip_attr_agi": (40,),
    "equip_attr_wisd": (41,),
    "equip_attr_will": (42,),
    "equip_attr_max_hp": (1,),
    "equip_attr_atk": (2,),
    "equip_attr_critical_rate": (9,),
    "equip_attr_normal_attack_damage_increase": (17,),
    "equip_attr_ultimate_skill_damage_increase": (28,),
    "equip_attr_heal_output_increase": (29,),
    "equip_attr_normal_skill_damage_increase": (32,),
    "equip_attr_combo_skill_damage_increase": (33,),
    "equip_attr_ultimate_sp_gain_scalar": (44,),
    "equip_attr_physical_damage_increase": (50,),
    "equip_attr_damage_to_broken_unit_increase": (61,),
    "equip_attr_physical_and_spellInfliction_enhance": (87,),
    "equip_attr_cryst_and_pulse_damage_increase": (52, 53),
    "equip_fire_and_natural_damage_increase": (51, 54),
    "equip_spell_damage_increase": (51, 52, 53, 54),
    "equip_all_skill_damage_increase": (28, 32, 33),
    "equip_attr_all_damage_taken_scalar": (4, 5, 6, 7, 48, 60),
    "equip_main": (MAIN,),
    "equip_sub": (SUB,),
}


def avatar_entry(data: GameData, op) -> dict:
    nodes = [t.id for t in op.char_data.ability_talents] + (op.talent.attr_nodes if op.talent else [])
    for node in nodes:
        found = data.avatar_by_str.get(node.rsplit("_", 1)[0])
        if found:
            return found[1]
    raise MissingGameData("operator", op.name)


def _gear_item(data: GameData, equip) -> dict:
    d = equip.equip_data
    suit = ""
    if d.suit:
        suit = data.suit_by_name.get(d.suit.name)
        if suit is None:
            raise MissingGameData("gear set", d.suit.name)
    slot = d.type.key.replace("equip_type_", "")
    rarity = int(d.rarity.key.rsplit("_", 1)[-1] or 0)
    groups = [set(GEAR_PROPS.get(p, ())) for p in d.properties if p]
    loose = None
    for item in data.items_by_group.get((suit, slot, rarity), []):
        mods = item["AttrModifiers"]
        if mods[0]["AttrType"] != DEF or round(mods[0]["Values"][0]) != round(d.base_attr_value):
            continue
        ids = [m["AttrType"] for m in mods[1:]]
        if sorted(ids) != sorted(i for g in groups for i in g):
            continue
        # pieces can share the same stats in a different order (int-heavy vs will-heavy gloves),
        # skport keeps the game's order so walk both lists side by side
        at, ordered = 0, True
        for group in groups:
            if set(ids[at:at + len(group)]) != group:
                ordered = False
                break
            at += len(group)
        if ordered:
            return item
        loose = loose or item
    if loose is not None:
        return loose
    raise MissingGameData("gear", d.name)


def _talents(op) -> list[Talent]:
    d = op.char_data
    out = []
    nodes = sorted(d.ability_talents, key=lambda t: t.id)
    if nodes:
        got = [t for t in nodes if op.talent_unlocked(t.id)]
        total = sum(float(m.group(1)) for t in got if (m := re.search(r"\+(\d+(?:\.\d+)?)", t.desc)))
        out.append(Talent(nodes[0].name, nodes[0].icon_url, len(got), len(nodes), "attribute", nodes[0].locked_icon_url,
                          amount(total)))
    for kind, group in (("combat", d.combat_talents), ("base", d.cultivation_talents)):
        lines: dict[str, list] = {}
        for t in sorted(group, key=lambda t: t.id):
            lines.setdefault(t.id.rpartition("_")[0], []).append(t)
        for tiers in lines.values():
            level = sum(op.talent_unlocked(t.id) for t in tiers)
            shown = tiers[max(level, 1) - 1]
            out.append(Talent(shown.name, shown.icon_url, level, len(tiers), kind, shown.locked_icon_url))
    return out


def build_from_skport(data: GameData, card, op, *, stats: bool = True) -> Build:
    base = card.base
    owner = Owner(base.name, base.uid, base.level, base.world_level, base.server_name)
    d = op.char_data

    skills = [Skill(s.name, s.type.value, s.icon_url, op.skill_level(s.id)) for s in d.skills]
    talents = _talents(op)

    weapon = None
    if op.weapon:
        w = op.weapon
        essence = None
        if w.gem and w.gem.gem_data:
            kind, _, effect = w.gem.name.replace("Â", "").partition("·")
            gem = w.gem.gem_data
            base = essence_base(gem.template_id)
            # skport only sends the badge, the capsule under it comes from enka
            terms = [EssenceTerm(t.name, t.cost) for t in w.gem.terms]
            essence = Essence(effect or kind, base or gem.icon, terms, gem.icon if base else "")
        weapon_skills = [WeaponSkill(_skill_name(s.name), s.level) for s in w.skills]
        weapon = Weapon(w.name, w.rarity, w.weapon_data.icon_url, w.level, w.refine_level, w.breakthrough_level, essence,
                        weapon_skills)

    tactical = None
    if op.tactical_item:
        tactical = Tactical(op.tactical_item.name, op.tactical_item.tactical_item_data.icon_url)

    build = Build(
        id=op.id,
        name=op.name,
        rarity=op.rarity,
        element=element_of(d),
        profession=english(d.profession, PROFESSION, str.upper),
        weapon_type=english(d.weapon_type, WEAPON_TYPE, str.title),
        level=op.level,
        promotion=op.evolve_phase,
        potential=op.potential_level,
        art=d.illustration_url,
        owner=owner,
        skills=skills,
        talents=talents,
        weapon=weapon,
        tactical=tactical,
        source="skport",
        element_icon=element_icon(element_of(d)),
    )

    if not stats:
        build.gear = [Gear(e.equip_data.type.value, e.equip_data.icon_url, rarity_of(e),
                           e.equip_data.suit.name if e.equip_data.suit else "", e.equip_data.base_attr_value)
                      for e in op.equips]
        return build

    avatar = avatar_entry(data, op)
    weapon_excel = None
    if op.weapon:
        found = data.weapon_by_name.get(op.weapon.name)
        if found is None:
            raise MissingGameData("weapon", op.weapon.name)
        weapon_excel = found[1]
        for skill, skill_id in zip(build.weapon.skills, weapon_excel["SkillList"]):
            skill.stat, skill.value = skill_effect(data, skill_id, skill.level, avatar)
    items = [(_gear_item(data, e), e.enhance) for e in op.equips]
    loadout = Loadout(
        avatar=avatar,
        level=op.level,
        potential=op.potential_level,
        attr_nodes=op.talent.attr_nodes if op.talent else [],
        passive_nodes=op.talent.latest_passive_skill_nodes if op.talent else [],
        weapon=weapon_excel,
        weapon_level=op.weapon.level if op.weapon else 1,
        weapon_skill_levels=[s.level for s in op.weapon.skills] if op.weapon else [],
        gear=items,
    )
    build.stats = calculate(data, loadout)
    build.gear = [
        Gear(e.equip_data.type.value, e.equip_data.icon_url, rarity_of(e),
             e.equip_data.suit.name if e.equip_data.suit else "", g.defense, g.lines)
        for e, g in zip(op.equips, gear_stats(loadout))
    ]
    return build


def _skill_name(name: str) -> str:
    return re.sub(r"\s*\[[A-Z]\]$", "", name.split(":")[0]).strip()


def english(tag, table, case) -> str:
    return table.get(case(tag.key.rsplit("_", 1)[-1]), tag.value)


def element_of(char_data) -> str:
    return english(char_data.element, ELEMENT, str.title)


def rarity_of(equip) -> int:
    return int(equip.equip_data.rarity.key.rsplit("_", 1)[-1] or 0)


def player_from_skport(card) -> Player:
    base = card.base
    picked = [c.id for c in card.showcased]
    rest = sorted((c for c in card.chars if c.id not in picked),
                  key=lambda c: (-c.rarity, -c.level, -c.evolve_phase, -c.potential_level, c.name))
    roster = []
    for op in [*card.showcased, *rest]:
        weapon = op.weapon
        roster.append(Rostered(
            name=op.name,
            rarity=op.rarity,
            element=element_of(op.char_data),
            element_icon=element_icon(element_of(op.char_data)),
            portrait=op.char_data.avatar_rt_url or op.char_data.avatar_sq_url,
            level=op.level,
            potential=op.potential_level,
            promotion=op.evolve_phase,
            profession=english(op.char_data.profession, PROFESSION, str.upper),
            weapon_icon=weapon.weapon_data.icon_url if weapon else "",
            weapon_rarity=weapon.rarity if weapon else 0,
        ))
    by_id = {m.achievement_data.id: m for m in card.achieve.medals}
    medals = [Badge(m.name, m.icon, m.level, m.is_plated, int(slot))
              for slot, medal_id in card.achieve.display.items() if (m := by_id.get(medal_id))]
    medals.sort(key=lambda b: b.slot)
    return Player(
        name=base.name,
        uid=base.uid,
        level=base.level,
        world_level=base.world_level,
        region=base.server_name,
        avatar=base.avatar_url,
        mission=base.main_mission.description,
        created=base.create_time,
        operators_owned=base.char_num,
        weapons_owned=base.weapon_num,
        files=base.doc_num,
        medals=medals,
        regions=[(d.name, d.level) for d in card.domain],
        roster=roster,
        source="skport",
    )
