from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from akef import Client

DATA = Path(__file__).parent / "data"


def load(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


ROUTES = {
    "/user/oauth2/v2/grant": {"status": 0, "msg": "OK", "data": {"uid": "G1000000001", "code": "fakecode"}},
    "/user/info/v1/basic": {
        "status": 0,
        "msg": "OK",
        "data": {"hgId": "1000000001", "email": "en*****in@mail.com", "nickName": "", "realEmail": "secret@mail.com",
                 "ageGate": {"regionCode": "JP"}},
    },
    "/web/v1/user/auth/generate_cred_by_code": "cred",
    "/web/v1/auth/refresh": {"code": 0, "message": "OK", "data": {"token": "0123456789abcdef0123456789abcdef"}},
    "/api/v1/game/player/binding": "binding",
    "/api/v1/game/endfield/card/detail": "card_detail",
    "/api/v1/game/endfield/card/indie-hard": "indie_hard",
    "/web/v1/game/endfield/team/user-game-data": "user_game_data",
    "/web/v1/wiki/item/catalog": "wiki_weapons",
    "/bulletin/v2/aggregate": "news",
    "/web/v1/game/endfield/enums": "enums",
    "/web/v1/game/endfield/attendance": "attendance",
    "/web/v1/wiki/char-pool": "char_pool",
    "/web/v1/wiki/weapon-pool": "weapon_pool",
    "/web/v2/user": "user",
}


class FakeClient(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls: list[tuple[str, str, dict, str | None]] = []
        self.fail_next: list[int] = []
        self.checked_in = False

    async def _send(self, method, url, headers, body=None):
        self.calls.append((method, url, headers, body))
        path = urlsplit(url).path
        if headers.get("cred") == "dead" and path.startswith(("/api", "/web/v1/game", "/web/v2")):
            # what skport sends once a login has expired
            return 200, json.dumps({"code": 10001, "message": "No valid user information found"})
        if method == "POST" and path == "/web/v1/game/endfield/attendance":
            if self.checked_in:
                return 200, json.dumps({"code": 10001, "message": "Please do not sign in again!", "data": None})
            self.checked_in = True
            return 200, json.dumps(load("check_in"))
        if self.fail_next and path.startswith(("/api", "/web/v1/game", "/web/v2", "/web/v1/wiki")):
            return self.fail_next.pop(0), ""
        if path == "/api/v1/game/endfield/card/char":
            wanted = parse_qs(urlsplit(url).query)["charId"][0]
            chars = load("card_detail")["data"]["detail"]["chars"]
            found = next((ch for ch in chars if ch["id"] == wanted), None)
            return 200, json.dumps({"code": 0, "message": "OK", "data": {"detail": found}})
        route = ROUTES[path]
        return 200, json.dumps(load(route) if isinstance(route, str) else route)


@pytest.fixture
def client():
    return FakeClient("fake-account-token")
