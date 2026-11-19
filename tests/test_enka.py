import json
import shutil
from pathlib import Path

import pytest

import akef
from akef.enka import GameData, build_from_skport, player_from_skport, profile_from_enka
from akef.models.card import tier_unlocked
from akef.enka.gamedata import language
from akef.enka.profile import talent_icon
from akef.wiki import wiki_page

DATA = Path(__file__).parent / "data"

# what enka.network shows for these operators (scraped from the site)
ENKA = {
    "Si": dict(strength=274, agility=100, intellect=688, will=100, hp=6865, atk=5673, defense=140,
               treatment_received=0.10, ult_gain=1.334, cryo_dmg=0.433),
    "Liino": dict(strength=89, agility=164, intellect=139, will=1250, hp=5940, atk=6130, defense=140,
                  treatment_bonus=0.664, treatment_received=1.25, ult_gain=1.407),
    "Arcane": dict(strength=91, agility=93, intellect=430, will=765, hp=6950, atk=4802, defense=140,
                   treatment_received=0.765, ult_gain=1.892),
    "Yvonne": dict(strength=82, agility=312, intellect=671, will=105, hp=5905, atk=4112, defense=140,
                   crit_rate=0.564, treatment_received=0.105, cryo_dmg=0.256),
}


def shown(value):
    return f"{(value + 1e-4) * 100:.1f}%" if isinstance(value, float) else value


def player_json():
    return json.loads((DATA / "enka" / "player.json").read_text(encoding="utf-8"))


def skport_card():
    return akef.Card.model_validate(json.loads((DATA / "card_detail.json").read_text(encoding="utf-8"))["data"]["detail"])


@pytest.fixture
async def data(tmp_path):
    shutil.copytree(DATA / "enka", tmp_path, dirs_exist_ok=True)
    game = GameData(tmp_path)
    await game.load()
    return game


@pytest.fixture
async def profile(data):
    return await profile_from_enka(data, player_json())


async def test_enka_profile(profile):
    assert profile.owner.name == "Endmin"
    assert profile.owner.uid == "4000000001"
    assert [b.name for b in profile.builds] == ["Si", "Liino", "Arcane", "Yvonne"]


@pytest.mark.parametrize("name", list(ENKA))
async def test_enka_stats_match_the_site(profile, name):
    stats = profile.build(name).stats
    for field, want in ENKA[name].items():
        assert shown(getattr(stats, field)) == shown(want), field


async def test_enka_build_details(profile):
    arcane = profile.build("Arcane")
    assert [s.level for s in arcane.skills] == [10, 11, 11, 12]
    assert arcane.weapon.name == "Type 42: Solemn Phalanx"
    assert arcane.weapon.essence.name == "Detonate"
    assert arcane.gear_set == ("Eternal Xiranite", 4)
    gloves = arcane.gear[1]
    assert (gloves.slot, gloves.defense) == ("Gloves", 42)
    assert [(l.name, l.text, l.level) for l in gloves.lines] == [
        ("Will", "+84", 3), ("Intellect", "+55", 3), ("Ult Gain", "+26.7%", 3)]
    assert sum(t.unlocked for t in arcane.talents) == len(arcane.talents)


async def test_skport_build_matches_enka(data):
    card = skport_card()
    build = build_from_skport(data, card, card.character("Arcane"))
    assert (build.stats.hp, build.stats.atk, build.stats.intellect, build.stats.will) == (6950, 4802, 430, 765)
    assert build.source == "skport"
    essence = build.weapon.essence
    assert essence.icon == "https://enka.network/ui/ef/itemicon/item_gem_rarity_5.png"
    assert essence.badge.startswith("https://static.skport.com/")


async def test_weapon_and_essence_stats_match(data, profile):
    card = skport_card()
    enka = profile.build("Arcane").weapon
    assert [(s.name, s.value, s.stat, s.level) for s in enka.skills] == [
        ("Intellect", "+156", "Intellect", 9), ("ULT Efficiency", "+46.4%", "Ult Gain", 9), ("Detonate", "+25.6%", "ATK", 4)]
    assert [(t.name, t.points) for t in enka.essence.terms] == [("Intellect", 6), ("ULT Efficiency", 6), ("Detonate", 3)]
    skport = build_from_skport(data, card, card.character("Arcane")).weapon
    assert [(s.value, s.stat, s.level) for s in skport.skills] == [(s.value, s.stat, s.level) for s in enka.skills]
    assert [t.points for t in skport.essence.terms] == [6, 6, 3]


async def test_both_sources_share_the_essence_base(data, profile):
    card = skport_card()
    skport = build_from_skport(data, card, card.character("Arcane")).weapon.essence
    assert skport.icon == profile.build("Arcane").weapon.essence.icon


async def test_element_icon_and_essence_badge(profile):
    si = profile.build("Si")
    assert si.element_icon.endswith("/attributeicon/CrystDamageIncrease.png")
    assert si.weapon.essence.badge.endswith(".png")
    assert si.element_icon in si.urls() and si.weapon.essence.badge in si.urls()


def test_tier_unlocked():
    latest = ["chr_x_passive_skill_0_2"]
    assert tier_unlocked("chr_x_passive_skill_0_1", latest)
    assert tier_unlocked("chr_x_passive_skill_0_2", latest)
    assert not tier_unlocked("chr_x_passive_skill_0_3", latest)
    assert not tier_unlocked("chr_x_passive_skill_1_1", latest)


def test_talent_icon_path():
    assert talent_icon("/ui/ef/icon_talent_x_01.png").endswith("/ui/ef/skillicon/icon_talent_x_01.png")
    assert talent_icon("/ui/ef/spaceshipskillicon/a.png").endswith("/ui/ef/spaceshipskillicon/a.png")


async def test_talents_group_like_the_game(profile):
    for build in profile.builds:
        kinds = [t.kind for t in build.talents]
        assert kinds[0] == "attribute" and kinds.count("attribute") == 1
        assert kinds == sorted(kinds, key=["attribute", "combat", "base"].index)
        attribute = build.talents[0]
        assert attribute.max_level == 4 and attribute.value.startswith("+")
        assert all(1 <= t.max_level <= 3 for t in build.talents[1:])
        done, total = build.talent_progress
        assert 0 <= done <= total


async def test_enka_player(profile):
    player = profile.player
    assert player.signature == "testing"
    assert [op.name for op in player.roster] == ["Si", "Liino", "Arcane", "Yvonne"]
    assert player.roster[0].promotion == 4
    assert player.roster[0].id.startswith("chr_")
    assert len(player.medals) == 10 and player.medals[0].icon.startswith("https://enka.network/ui/ef/medalicon/")
    assert player.regions == [("Valley IV", 12), ("Wuling", 30)]
    assert player.avatar.endswith(".png") and player.namecard.endswith(".png")


def test_skport_player_keeps_the_showcase_first():
    card = skport_card()
    player = player_from_skport(card)
    picked = [c.name for c in card.showcased]
    assert [op.name for op in player.roster[:len(picked)]] == picked
    assert len(player.roster) == len(card.chars)


async def test_enka_answers_are_reused(monkeypatch, data):
    from akef.enka import client as module

    calls = []

    async def fake_fetch(uid):
        calls.append(uid)
        return player_json()

    monkeypatch.setattr(module, "fetch_player", fake_fetch)
    enka = akef.Enka(data=data)
    await enka.profile(1)
    await enka.profile(1)
    assert calls == [1]
    await akef.Enka(data=data, cache=False).profile(1)
    assert calls == [1, 1]


async def test_unknown_operator_on_the_card(data):
    with pytest.raises(akef.UnknownCharacter):
        await akef.Enka(data=data).build(skport_card(), "Nobody")


def test_language_codes():
    assert language("ja") == language("JP") == ("ja", "JP")
    assert language("zh_Hant") == ("zh-tw", "CHT")
    assert language("EN") == ("en", "EN")
    with pytest.raises(ValueError):
        language("klingon")


async def test_names_match_in_any_language(data):
    locs = data._tables["locs"]
    weapon = next(iter(data.weapons.values()))
    for names in locs.values():
        name = names.get(str(weapon["NameHash"]))
        if name:
            assert data.weapon_by_name[name][1] is weapon


def test_wiki_page():
    doc = {"blockIds": ["a", "b"], "blockMap": {"a": {"text": {"inlineElements": [{"text": {"text": "\"Quote.\""}}]}},
                                                 "b": {"text": {"inlineElements": [{"text": {"text": "Bio."}}]}}}}
    item = akef.WikiItem.model_validate({
        "itemId": "1", "name": "Arcane", "brief": {"description": doc},
        "document": {"documentMap": {"d": doc},
                     "chapterGroup": [{"title": "Ability Matrix", "widgets": [{"id": "w", "title": "//Combat Skills"}]}],
                     "widgetCommonMap": {"w": {"tableList": [{"label": "Codename", "value": "Arcane"}, {"label": "Race", "value": "Liberi"}],
                                               "tabList": [], "tabDataMap": {"t": {"intro": {"name": "Gloompurge (Array Arcana: INT)", "type": "Ultimate", "description": "d"}}}}}},
    })
    page = wiki_page(item)
    assert (page.quote, page.bio, page.info) == ("Quote.", "Bio.", [("Race", "Liberi")])
    assert page.skills[0].name == "Gloompurge"
    assert akef.WikiPart.TALENTS.needs_index and not akef.WikiPart.LORE.needs_index
