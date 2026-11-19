import pytest

from akef import AlreadyCheckedIn, APIError, AuthError, NoRoleError, UnknownCharacter


async def test_check_in_then_already_checked_in(client):
    result = await client.check_in()
    assert [r.name for r in result.rewards] == ["Oroberyl", "Intermediate Combat Record"]
    assert result.rewards[0].count == 90
    assert result.tomorrow[0].name == "Arms INSP Kit"
    method, _, headers, body = client.calls[-1]
    assert method == "POST" and body == "{}"
    assert headers["sk-game-role"] == "3_4000000001_2"

    with pytest.raises(AlreadyCheckedIn) as err:
        await client.check_in()
    assert err.value.code == 10001
    assert isinstance(err.value, APIError)


async def test_login_flow(client):
    await client.login()
    assert client.cred == "fakecredfakecredfakecredfakecred"
    assert client.salt == "0123456789abcdef0123456789abcdef"
    paths = [url for _, url, _, _ in client.calls]
    assert paths[0].endswith("/user/oauth2/v2/grant")
    assert paths[1].endswith("/generate_cred_by_code")
    assert len(paths) == 2


async def test_logs_in_lazily(client):
    roles = await client.roles()
    assert roles[0].uid == "4000000001"
    assert roles[0].game_role == "3_4000000001_2"
    assert client.logged_in


async def test_card_sends_role_and_sign(client):
    card = await client.card()
    assert card.name == "Endmin"
    method, url, headers, _ = client.calls[-1]
    assert url.endswith("/card/detail?roleId=4000000001&serverId=2")
    assert headers["sk-game-role"] == "3_4000000001_2"
    assert headers["cred"] == client.cred
    assert len(headers["sign"]) == 32


async def test_unknown_uid(client):
    with pytest.raises(NoRoleError):
        await client.card(123)


async def test_relogin_once_on_401(client):
    await client.login()
    client.fail_next = [401]
    banners = await client.char_banners()
    assert banners
    grants = [u for _, u, _, _ in client.calls if u.endswith("/grant")]
    assert len(grants) == 2


async def test_gives_up_after_second_401(client):
    await client.login()
    client.fail_next = [401, 401]
    with pytest.raises(AuthError):
        await client.enums()


async def test_account_hides_real_email(client):
    account = await client.account()
    assert account.region == "JP"
    assert "realEmail" not in account.model_dump(by_alias=True)
    assert not hasattr(account, "real_email")


async def test_raw_returns_untouched_data(client):
    card = await client.card(raw=True)
    assert card["detail"]["base"]["roleId"] == "4000000001"
    assert "calendar" in await client.attendance(raw=True)
    assert "list" in await client.roles(raw=True)
    assert "list" in await client.char_banners(raw=True)
    assert "list" in await client.weapon_banners(raw=True)
    assert "professions" in await client.enums(raw=True)
    assert "user" in await client.profile(raw=True)
    assert (await client.account(raw=True))["hgId"] == "1000000001"


async def test_everything_parses(client):
    assert (await client.attendance()).calendar
    assert await client.weapon_banners()
    assert (await client.enums()).label("weapon_type_sword") == "Sword"
    assert (await client.profile()).id


async def test_character_by_name_id_or_list(client):
    arcane = await client.character("arcane")
    assert arcane.name == "Arcane"
    by_id = await client.character(arcane.id)
    assert by_id.id == arcane.id
    both = await client.character(["Arcane", "laevatain"])
    assert [c.name for c in both] == ["Arcane", "Laevatain"]
    lookups = [u for _, u, _, _ in client.calls if "/card/detail" in u]
    assert len(lookups) == 1


async def test_character_typo_suggests_a_name(client):
    with pytest.raises(UnknownCharacter, match="did you mean 'Laevatain'"):
        await client.character("laevatian")


async def test_character_raw(client):
    raw = await client.character(["Arcane"], raw=True)
    assert raw[0]["detail"]["charData"]["name"] == "Arcane"


async def test_monument(client):
    monument = await client.monument()
    first = monument.groups[0]
    assert first.name == "Murmurs of the Deep Forest"
    assert first.cleared == (4, 0)
    assert first.achieve.level == 1
    stage = first.dungeon_groups[0].normal_dungeon
    assert stage.recommend_level == 60 and stage.enemies
    assert len(stage.best_record.chars) == 4
    assert stage.best_record.cleared_at.year >= 2026
    assert stage.best_record.seconds == 68
    assert all("<@" not in rule for rule in stage.rules)
    url = client.calls[-1][1]
    assert url.endswith("/card/indie-hard?roleId=4000000001&serverId=2")


async def test_relogin_when_the_login_died(client):
    await client.login()
    client.cred = "dead"
    roles = await client.roles()
    assert roles and client.cred != "dead"


async def test_check_in_after_the_login_died(client):
    await client.login()
    client.cred = "dead"
    result = await client.check_in()
    assert result.rewards
    with pytest.raises(AlreadyCheckedIn):
        await client.check_in()


async def test_login_file_skips_logging_in(tmp_path):
    from tests.conftest import FakeClient

    file = tmp_path / "login.json"
    first = FakeClient("token", login_file=file)
    await first.roles()
    second = FakeClient("token", login_file=file)
    assert second.logged_in and second.cred == first.cred
    await second.roles()
    assert not any(u.endswith("/grant") for _, u, _, _ in second.calls)
    assert not FakeClient("other token", login_file=file).logged_in


async def test_character_by_name_needs_one_request(client):
    await client.character("Arcane")
    chars = [u for _, u, _, _ in client.calls if "/card/" in u]
    assert len(chars) == 1 and "/card/detail" in chars[0]


async def test_cache_reuses_answers(client):
    await client.card()
    await client.card()
    assert len([u for _, u, _, _ in client.calls if "/card/detail" in u]) == 1
    client.clear_cache()
    await client.card()
    assert len([u for _, u, _, _ in client.calls if "/card/detail" in u]) == 2


async def test_same_request_at_once_goes_out_once(client):
    import asyncio

    await client.roles()
    await asyncio.gather(*(client.card() for _ in range(5)))
    assert len([u for _, u, _, _ in client.calls if "/card/detail" in u]) == 1


async def test_check_in_refreshes_attendance(client):
    await client.attendance()
    await client.check_in()
    await client.attendance()
    assert len([u for m, u, _, _ in client.calls if m == "GET" and "/attendance" in u]) == 2


async def test_cache_can_be_turned_off():
    from tests.conftest import FakeClient

    client = FakeClient("token", cache=False)
    await client.card()
    await client.card()
    assert len([u for _, u, _, _ in client.calls if "/card/detail" in u]) == 2


async def test_pulls_after_a_date_stops_early(client):
    pages = {
        "": {"list": [{"seqId": "3", "gachaTs": "1793000000000", "rarity": 4}, {"seqId": "2", "gachaTs": "1792000000000", "rarity": 6}], "hasMore": True},
        "2": {"list": [{"seqId": "1", "gachaTs": "1780000000000", "rarity": 4}], "hasMore": False},
    }
    asked = []

    async def fake(method, url, *, params=None, payload=None):
        asked.append(params.get("seq_id", ""))
        return pages[params.get("seq_id", "")]

    client._plain = fake
    rows = await client._pull_pages("/api/record/char", {}, 0, 1790000000000)
    assert [r["seqId"] for r in rows] == ["3", "2"]
    assert asked == ["", "2"]


async def test_news(client):
    news = await client.news()
    assert len(news) == 3
    assert news[0].start_at >= news[-1].start_at
    assert news[0].header and news[0].image.startswith("https://")
    assert "<" not in news[0].text


async def test_inventory_names_what_it_can(client):
    inv = await client.inventory()
    assert len(inv.operators) == 6 and len(inv.weapons) == 8
    assert any(o.name for o in inv.operators)
    assert [o.name for o in inv.operators if o.name] == sorted(o.name for o in inv.operators if o.name)
    assert sum(g.count for g in inv.gear) >= len(inv.gear)
    raw = await client.inventory(raw=True)
    assert raw["roleId"] == "4000000001"


async def test_wiki(client):
    weapons = await client.wiki("weapons")
    assert weapons and weapons[0].name and weapons[0].cover
    with pytest.raises(ValueError):
        await client.wiki("nope")


async def test_debug_log_hides_queries(caplog):
    import logging

    from akef import Client

    class Response:
        status = 200

        async def text(self):
            return "{}"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

    class Session:
        closed = False

        def request(self, *args, **kwargs):
            return Response()

    client = Client("token", session=Session(), debug=True)
    with caplog.at_level(logging.INFO, logger="akef"):
        await client._send("GET", "https://example.com/card/detail?token=secret", {})
    messages = [r.getMessage() for r in caplog.records]
    assert any("/card/detail -> 200" in m for m in messages)
    assert not any("secret" in m for m in messages)


async def test_pulls_refuse_another_uids_history(client):
    from akef import Pulls

    role = await client.role()
    with pytest.raises(ValueError, match="belong to UID"):
        await client.pulls(since=Pulls(uid=str(int(role.uid) + 1)))
