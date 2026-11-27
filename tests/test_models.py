from datetime import datetime, timezone

from akef import Attendance, Banner, Card, Enums, Profile
from tests.conftest import load


def card() -> Card:
    return Card.model_validate(load("card_detail")["data"]["detail"])


def test_card_base():
    c = card()
    assert c.uid == "4000000001"
    assert c.name == "Endmin"
    assert c.base.level == 60
    assert c.base.world_level == 7
    assert isinstance(c.base.create_time, datetime)
    assert c.base.awakening_days > 0


def test_card_live_stats():
    c = card()
    assert c.stamina.current == c.stamina.max == 360
    assert c.stamina.full_at is None
    assert c.stamina.is_full
    assert c.stamina.seconds_left == 0
    assert (c.daily.current, c.daily.max) == (20, 100)
    assert c.battle_pass.cur_level == 60
    assert c.weekly.total == 10


def test_character():
    arcane = card().character("arcane")
    assert arcane is not None
    assert arcane.rarity == 6
    assert arcane.profession == "Caster"
    assert arcane.element == "Nature"
    assert arcane.evolve_phase == 4
    assert arcane.weapon.name.startswith("Type 42")
    assert arcane.weapon.breakthrough_level == 4
    assert len(arcane.equips) == 4
    assert arcane.tactical_item.name == "Yazhen Powder"
    assert len(arcane.char_data.skills) == 4
    skill = arcane.char_data.skills[0]
    assert arcane.skill_level(skill.id) == 10


def test_lower_tiers_unlocked():
    arcane = card().character("arcane")
    assert len(arcane.talents) == 12
    assert len(arcane.unlocked_talents) == 12
    assert arcane.talent_unlocked("chr_0032_lizhiyan_passive_skill_0_1")
    assert arcane.talent_unlocked("spaceship_skill_chr_0032_lizhiyan_1_1")
    assert not arcane.talent_unlocked("chr_0032_lizhiyan_passive_skill_0_3")
    assert not arcane.talent_unlocked("chr_9999_nobody_passive_skill_0_1")


def test_endgame_sections():
    c = card()
    contract = c.crisis_contract[0]
    assert contract.highest == 11
    assert contract.indicator_mission.count == 3
    season = c.war_echoes.seasons[0]
    assert season.name == "Season of Fervor"
    assert season.weeks[0].dungeon_groups
    assert c.indie_hard.groups
    assert c.seek_suspicion.done


def test_world():
    c = card()
    valley = c.domain[0]
    assert valley.name == "Valley IV"
    assert valley.settlements[0].name == "Refugee Camp"
    assert valley.areas[0].puzzle_count.done
    assert c.space_ship.rooms
    assert c.achieve.count == 128
    assert c.achieve.showcased


def test_attendance():
    a = Attendance.model_validate(load("attendance")["data"])
    assert len(a.calendar) == 30
    today = a.today
    assert today is not None
    reward = a.reward(today)
    assert reward.name == "Intermediate Combat Record"
    assert reward.count == 2
    credits = a.resource_info_map["endfield_attendance_7_2000"]
    assert credits.display_name == "Talosian Credit Notes"


def test_banners():
    chars = [Banner.model_validate(b) for b in load("char_pool")["data"]["list"]]
    weapons = [Banner.model_validate(b) for b in load("weapon_pool")["data"]["list"]]
    assert chars[0].items[0].stars == 6
    assert chars[0].items[0].featured
    assert len(weapons) == 2 and weapons[0].items
    assert chars[0].ends_at() == datetime.fromtimestamp(1795557600, tz=timezone.utc)
    assert chars[0].ends_at("eu") == datetime.fromtimestamp(1795510800, tz=timezone.utc)


def test_enums():
    e = Enums.model_validate(load("enums")["data"])
    assert "professions" in e.groups()
    assert e.label("profession_caster") == "Caster"
    assert e.label("nope") is None


def test_profile():
    p = Profile.model_validate(load("user")["data"])
    assert p.id == "8000000000001"
    assert p.user_rts.fans == 0


def test_showcase_order():
    card = Card.model_validate(load("card_detail")["data"]["detail"])
    assert [c.id for c in card.showcased] == card.config.char_ids[:len(card.showcased)]
    assert card.showcased[0].name == "Arcane"


def pulls():
    from akef import Pull, Pulls

    raw = load("pulls")
    ops = [Pull.model_validate(dict(r, banner=k.lower())) for k, rows in raw["chars"].items() for r in rows]
    weapons = [Pull.model_validate(dict(r, banner=r.get("poolType", ""))) for r in raw["weapons"]]
    return Pulls(
        operators=sorted((p for p in ops if p.kind == "draw"), key=lambda p: p.seq_id),
        weapons=sorted(weapons, key=lambda p: p.seq_id),
        gifts=[p for p in ops if p.kind != "draw"],
    )


def test_pull_fields():
    first = pulls().operators[0]
    assert first.name and first.item_id.startswith("chr_")
    assert first.pulled_at.tzinfo is not None and first.pulled_at.year == 2026


def test_pity_per_banner():
    p = pulls()
    by_name = {(x.name, x.banner): x for x in p.pity()}
    limited = next(x for x in p.pity() if x.name == "Limited operators")
    assert (limited.since_six, limited.hard, limited.featured_at) == (5, 80, 120)
    assert by_name["Standard", "Basic Headhunting"].since_six == 15
    assert by_name["Weapons", "Moongleam Issue"].since_six == 6
    assert len(p.gifts) == 3


def test_free_pulls():
    from akef import Pull, since_last

    rows = [Pull(rarity=6), Pull(rarity=4), Pull(rarity=4, is_free=True), Pull(rarity=5)]
    assert since_last(rows) == 2


def test_sanity_at():
    from datetime import timedelta

    c = card()
    c.stamina.current, c.stamina.max = 100, 200
    c.stamina.full_at = c.current_ts + timedelta(minutes=100)
    assert c.sanity_at(150) == c.current_ts + timedelta(minutes=50)
    assert c.sanity_at(50) == c.current_ts
    assert c.sanity_at(500) is None


def test_wiki_page_reading():
    from akef import WikiItem

    doc = {"blockIds": ["a"], "blockMap": {"a": {"text": {"inlineElements": [{"text": {"text": "Hits hard."}}]}, "childIds": ["b"]},
                                            "b": {"text": {"inlineElements": [{"text": {"text": "Twice."}}]}}}}
    item = WikiItem.model_validate({
        "itemId": "1", "name": "Arcane",
        "brief": {"cover": "c.png", "description": doc},
        "document": {
            "extraInfo": {"illustration": "art.png"},
            "documentMap": {"d1": doc},
            "chapterGroup": [{"title": "Ability Matrix", "widgets": [{"id": "w", "title": "//Combat Skills"}]}],
            "widgetCommonMap": {"w": {"tableList": [{"label": "Element", "value": "Nature"}],
                                      "tabList": [{"tabId": "t", "icon": "i.png"}],
                                      "tabDataMap": {"t": {"intro": {"name": "Gloompurge", "type": "Ultimate", "description": "d1"}}}}},
        },
    })
    assert item.illustration == "art.png" and item.description == "Hits hard.\nTwice."
    assert item.info == [("Element", "Nature")]
    skill = item.sections[0].entries[0]
    assert (skill.name, skill.kind, skill.icon, skill.text) == ("Gloompurge", "Ultimate", "i.png", "Hits hard.\nTwice.")


def test_wiki_tables():
    from akef import WikiItem

    blocks = {
        "t": {"kind": "table", "table": {"rowIds": ["r"], "columnIds": ["a", "b"], "cellMap": {
            "r_a": {"childIds": ["x", "y"]}, "r_b": {"childIds": ["z"]}}}},
        "x": {"kind": "text", "text": {"inlineElements": [{"text": {"text": "Potential"}}]}},
        "y": {"kind": "text", "text": {"inlineElements": [{"text": {"text": "01"}}]}},
        "z": {"kind": "text", "text": {"inlineElements": [{"kind": "entry", "entry": {"id": "109", "count": "5"}}]}},
    }
    item = WikiItem.model_validate({"itemId": "1", "document": {"documentMap": {"d": {"blockIds": ["t"], "blockMap": blocks}}}})
    [table] = item.content("d")
    assert table.rows[0][0].text == "Potential\n01"
    assert (table.rows[0][1].links[0].id, table.rows[0][1].links[0].count) == ("109", 5)


def test_pulls_json(tmp_path):
    from akef import Pull, Pulls

    pulls = Pulls(
        uid="4727743200",
        operators=[Pull.model_validate({"charName": "Yvonne", "charId": "chr_1", "rarity": 6, "gachaTs": "1760000000000",
                                        "seqId": 12, "poolId": "special_1", "poolName": "Banner", "banner": "special"})],
        weapons=[Pull.model_validate({"weaponName": "Artzy Tyrannical", "rarity": 6, "gachaTs": "1760000100000",
                                      "poolId": "weapon_1", "seqId": 3})],
    )
    back = Pulls.load(pulls.save(tmp_path / "pulls.json"))
    assert back == pulls
    assert back.operators[0].pulled_at == pulls.operators[0].pulled_at
    assert back.last_seq == {"special": 12, "weapon_1": 3}
    assert '"name": "Yvonne"' in pulls.to_json()
    assert Pulls.load(pulls.save(tmp_path / "pulls.csv")) == pulls
    header, first = pulls.to_csv().splitlines()[:2]
    assert header.startswith("uid,group,kind,banner") and first.startswith("4727743200,operators,draw,special")


def test_contract_detail():
    from akef import ContractDetail
    from akef.models.card import fill

    raw = load("crisis_contract")["crisisContract"]
    detail = ContractDetail.model_validate(raw)
    assert detail.best.is_best and len(detail.best.chars) == 4 and detail.best.seconds > 0
    assert len(detail.history.records) >= 1 and detail.stage.enemies
    assert all("{" not in i.text and "<" not in i.text for i in detail.indicators)
    assert fill("Enemy HP <color=#cc9900>+{hp_up:0%}</color>.", {"hp_up": "1.2"}) == "Enemy HP +120%."
    assert fill("Timer -{-time:0}s.", {"time": "-45"}) == "Timer -45s."
