from __future__ import annotations

import asyncio
import difflib
import hashlib
import json
import logging
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import aiohttp

from akef import constants as c
from akef.cache import TTLCache
from akef.errors import AlreadyCheckedIn, APIError, AuthError, NetworkError, NoRoleError, UnknownCharacter
from akef.models import (
    OPERATOR_BANNERS,
    Account,
    Attendance,
    Banner,
    Card,
    Character,
    CheckIn,
    ContractDetail,
    Enums,
    IndieHard,
    Inventory,
    Notice,
    Owned,
    Profile,
    Pull,
    Pulls,
    Role,
    WikiItem,
)
from akef.signing import sign

ALREADY_CHECKED_IN = 10001
# same code skport uses for "already checked in"
LOGIN_GONE = 10001
ATTENDANCE = "/web/v1/game/endfield/attendance"
CACHE_FOR = {
    "/api/v1/game/endfield/card/detail": 60,
    "/api/v1/game/endfield/card/char": 60,
    "/api/v1/game/endfield/card/indie-hard": 300,
    "/api/v1/game/endfield/card/crisis-contract": 300,
    ATTENDANCE: 60,
    "/web/v2/user": 300,
    "/web/v1/game/endfield/enums": 3600,
    "/web/v1/wiki/char-pool": 600,
    "/web/v1/wiki/weapon-pool": 600,
    "/web/v1/wiki/item/catalog": 3600,
    "/web/v1/wiki/item/info": 3600,
    "/web/v1/game/endfield/team/user-game-data": 60,
}
WIKI = {"operators": 1, "weapons": 2, "threats": 3, "gear": 4, "facilities": 5, "items": 6, "essence": 15, "valuables": 16}
NEWS_LANG = {"en": "en-us", "ja": "ja-jp", "ko": "ko-kr", "zh_Hant": "zh-tw"}

log = logging.getLogger("akef")
CHAR_ID = re.compile(r"[0-9a-f]{32}")


def _key(name: str) -> str:
    return re.sub(r"[\W_]+", "", name.casefold())


def _json(text: str) -> dict:
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


class Client:
    def __init__(
        self,
        token: str,
        *,
        lang: str = "en",
        session: aiohttp.ClientSession | None = None,
        timeout: float = 20,
        login_file: str | Path | None = None,
        cache: bool = True,
        debug: bool = False,
    ):
        self.token = token.strip()
        self.lang = lang
        self.cred: str | None = None
        self.salt: str | None = None
        self.user_id: str | None = None
        self._session = session
        self._owns_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._login_lock = asyncio.Lock()
        self._roles: list[Role] | None = None
        self._names: dict[str, dict[str, tuple[str, str]]] = {}
        self.login_file = Path(login_file) if login_file else None
        self.cache = cache
        self.debug = debug
        self._cache = TTLCache()
        self._load_login()

    async def __aenter__(self) -> "Client":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
            self._owns_session = True
        return self._session

    def _fingerprint(self) -> str:
        return hashlib.sha256(self.token.encode()).hexdigest()

    def _load_login(self) -> None:
        if self.login_file is None:
            return
        try:
            saved = json.loads(self.login_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if saved.get("token") == self._fingerprint():
            self.cred, self.salt, self.user_id = saved.get("cred"), saved.get("salt"), saved.get("user_id")
            if saved.get("roles") is not None:
                self._roles = [Role.model_validate(r) for r in saved["roles"]]

    def _save_login(self) -> None:
        if self.login_file is None:
            return
        data = {"token": self._fingerprint(), "cred": self.cred, "salt": self.salt, "user_id": self.user_id}
        if self._roles is not None:
            data["roles"] = [r.model_dump(by_alias=True, mode="json") for r in self._roles]
        try:
            self.login_file.parent.mkdir(parents=True, exist_ok=True)
            self.login_file.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass

    def clear_cache(self) -> None:
        self._cache.drop()

    @property
    def logged_in(self) -> bool:
        return self.cred is not None and self.salt is not None

    def _headers(self, account: bool = False) -> dict[str, str]:
        headers = {"User-Agent": c.USER_AGENT, "Origin": c.ORIGIN, "Referer": c.ORIGIN + "/"}
        headers["x-language" if account else "sk-language"] = self.lang
        return headers

    async def _send(self, method: str, url: str, headers: dict, body: str | None = None) -> tuple[int, str]:
        # queries can carry tokens, so only the path ever reaches the log or an error
        where = url.split("?", 1)[0]
        started = time.perf_counter()
        try:
            async with self.session.request(method, url, headers=headers, data=body) as resp:
                status, text = resp.status, await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if self.debug:
                log.warning("%s %s failed: %s", method, where, exc.__class__.__name__)
            raise NetworkError(f"{method} {where} failed: {exc.__class__.__name__}") from exc
        if self.debug:
            log.info("%s %s -> %s in %.0fms", method, where, status, (time.perf_counter() - started) * 1000)
        return status, text

    async def _account(self, method: str, path: str, *, params: dict | None = None, payload: dict | None = None):
        headers = self._headers(account=True)
        body = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":"))
            headers["Content-Type"] = "application/json"
        url = c.ACCOUNT_HOST + path + (f"?{urlencode(params)}" if params else "")
        status, text = await self._send(method, url, headers, body)
        data = _json(text)
        if status != 200 or data.get("status") != 0:
            raise AuthError(data.get("msg") or f"account token rejected (http {status})", code=data.get("status"))
        return data.get("data") or {}

    async def _zonai(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        payload: dict | None = None,
        role: Role | None = None,
        signed: bool = True,
        retry: bool = True,
    ) -> Any:
        if signed and not self.logged_in:
            await self.login()

        query = urlencode(params) if params else ""
        body = json.dumps(payload, separators=(",", ":")) if payload is not None else None
        headers = self._headers()
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.cred:
            headers["cred"] = self.cred
        if role is not None:
            headers["sk-game-role"] = role.game_role
        if signed:
            # GETs sign the query string, POSTs sign the json body
            headers.update(sign(path, body if body is not None else query, self.salt))

        url = c.ZONAI_HOST + path + (f"?{query}" if query else "")
        ttl = CACHE_FOR.get(path, 0) if self.cache and method == "GET" else 0
        if ttl:
            status, text = await self._cache.get(
                (url, headers.get("sk-game-role"), self.lang),
                ttl,
                lambda: self._send(method, url, headers, body),
                keep=lambda r: r[0] == 200 and _json(r[1]).get("code") == 0,
            )
        else:
            status, text = await self._send(method, url, headers, body)
        data = _json(text)

        # stale salt -> 401, dead cred -> 200 with code 10001
        gone = status == 401 or (data.get("code") == LOGIN_GONE and not (method == "POST" and path == ATTENDANCE))
        if gone and signed and retry:
            self.cred = self.salt = None
            await self.login()
            return await self._zonai(method, path, params=params, payload=payload, role=role, signed=signed, retry=False)
        if gone and signed:
            raise AuthError("skport refused the session", code=data.get("code", status))

        if status != 200 or data.get("code") != 0:
            raise APIError(data.get("message") or f"http {status}", code=data.get("code", status))
        return data.get("data")

    async def login(self) -> None:
        async with self._login_lock:
            if self.logged_in:
                return
            grant = await self._account(
                "POST", "/user/oauth2/v2/grant", payload={"token": self.token, "appCode": c.APP_CODE, "type": 0}
            )
            data = await self._zonai(
                "POST", "/web/v1/user/auth/generate_cred_by_code", payload={"kind": 1, "code": grant["code"]}, signed=False
            )
            self.cred = data["cred"]
            self.user_id = data.get("userId")
            self.salt = data.get("token") or await self.refresh()
            self._save_login()

    async def refresh(self) -> str:
        data = await self._zonai("GET", "/web/v1/auth/refresh", signed=False)
        self.salt = data["token"]
        return self.salt

    async def account(self, *, raw: bool = False) -> Account | dict:
        data = await self._account("GET", "/user/info/v1/basic", params={"token": self.token})
        return data if raw else Account.model_validate(data)

    async def profile(self, *, raw: bool = False) -> Profile | dict:
        data = await self._zonai("GET", "/web/v2/user")
        return data if raw else Profile.model_validate(data)

    async def roles(self, *, raw: bool = False) -> list[Role] | dict:
        data = await self._zonai("GET", "/api/v1/game/player/binding")
        if raw:
            return data
        roles = []
        for app in data.get("list") or []:
            if app.get("appCode") != "endfield":
                continue
            for binding in app.get("bindingList") or []:
                roles.extend(Role.model_validate(r) for r in binding.get("roles") or [])
        self._roles = roles
        self._save_login()
        return roles

    async def role(self, uid: int | str | None = None) -> Role:
        roles = self._roles if self._roles is not None else await self.roles()
        if not roles:
            raise NoRoleError("no Endfield account is bound to this SKPORT login")
        if uid is None:
            return next((r for r in roles if r.is_default), roles[0])
        found = next((r for r in roles if r.uid == str(uid)), None)
        if found is None:
            raise NoRoleError(f"UID {uid} isn't bound to this SKPORT login")
        return found

    async def card(self, uid: int | str | None = None, *, raw: bool = False) -> Card | dict:
        role = await self.role(uid)
        data = await self._zonai(
            "GET",
            "/api/v1/game/endfield/card/detail",
            params={"roleId": role.uid, "serverId": role.server_id},
            role=role,
        )
        return data if raw else Card.model_validate(data["detail"])

    async def character(
        self,
        who: str | list[str],
        uid: int | str | None = None,
        *,
        raw: bool = False,
    ) -> Character | dict | list[Character] | list[dict]:
        role = await self.role(uid)
        many = not isinstance(who, str)
        wanted = list(who) if many else [who]
        loaded: dict[str, dict] = {}
        ids = [await self._char_id(w, role, loaded) for w in wanted]

        async def one(char_id):
            if char_id in loaded:
                return {"detail": loaded[char_id]}
            return await self._zonai(
                "GET",
                "/api/v1/game/endfield/card/char",
                params={"roleId": role.uid, "serverId": role.server_id, "charId": char_id},
                role=role,
            )

        found = await asyncio.gather(*(one(i) for i in ids))
        out = []
        for name, data in zip(wanted, found):
            if not data.get("detail"):
                raise UnknownCharacter(f"{name!r} isn't on UID {role.uid}")
            out.append(data if raw else Character.model_validate(data["detail"]))
        return out if many else out[0]

    async def _char_id(self, who: str, role: Role, loaded: dict[str, dict]) -> str:
        if CHAR_ID.fullmatch(who):
            return who
        names = self._names.get(role.uid)
        if names is None or _key(who) not in names:
            card = await self.card(role.uid, raw=True)
            loaded.update({ch["id"]: ch for ch in card["detail"]["chars"]})
            names = {_key(ch["charData"]["name"]): (ch["id"], ch["charData"]["name"]) for ch in card["detail"]["chars"]}
            self._names[role.uid] = names
        if _key(who) in names:
            return names[_key(who)][0]
        close = difflib.get_close_matches(_key(who), names, n=1)
        hint = f", did you mean {names[close[0]][1]!r}?" if close else ""
        raise UnknownCharacter(f"no operator called {who!r} on UID {role.uid}{hint}")

    async def monument(self, uid: int | str | None = None, *, raw: bool = False) -> IndieHard | dict:
        role = await self.role(uid)
        data = await self._zonai(
            "GET",
            "/api/v1/game/endfield/card/indie-hard",
            params={"roleId": role.uid, "serverId": role.server_id},
            role=role,
        )
        return data if raw else IndieHard.model_validate(data["indieHard"])

    async def contract(self, uid: int | str | None = None, *, raw: bool = False) -> ContractDetail | dict:
        role = await self.role(uid)
        data = await self._zonai(
            "GET",
            "/api/v1/game/endfield/card/crisis-contract",
            params={"roleId": role.uid, "serverId": role.server_id},
            role=role,
        )
        return data if raw else ContractDetail.model_validate(data["crisisContract"])

    async def _gacha_token(self, role: Role) -> str:
        async def fetch():
            grant = await self._account(
                "POST", "/user/oauth2/v2/grant", payload={"token": self.token, "appCode": c.GACHA_APP_CODE, "type": 1}
            )
            # pull history wants the account-level uid, not the in-game one
            bindings = await self._plain("GET", c.BINDING_HOST + "/account/binding/v1/binding_list",
                                         params={"token": grant["token"], "appCode": "endfield"})
            account_uid = None
            for app in bindings.get("list") or []:
                for binding in app.get("bindingList") or []:
                    if any(r.get("roleId") == role.uid for r in binding.get("roles") or []):
                        account_uid = binding["uid"]
            if account_uid is None:
                raise NoRoleError(f"UID {role.uid} has no pull history on this login")
            data = await self._plain("POST", c.BINDING_HOST + "/account/binding/v1/u8_token_by_uid",
                                     payload={"uid": account_uid, "token": grant["token"]})
            return data["token"]

        return await self._cache.get(("gacha token", role.uid), 600, fetch)

    async def _plain(self, method: str, url: str, *, params: dict | None = None, payload: dict | None = None):
        headers = {"User-Agent": c.USER_AGENT}
        body = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":"))
            headers["Content-Type"] = "application/json"
        status, text = await self._send(method, url + (f"?{urlencode(params)}" if params else ""), headers, body)
        data = _json(text)
        if status != 200 or data.get("code", data.get("status", 0)) != 0:
            message = data.get("msg") or data.get("message") or f"http {status}"
            raise APIError(str(message), code=data.get("code", status))
        return data.get("data") or {}

    async def _pull_pages(self, path: str, params: dict, stop: int, after_ms: int) -> list[dict]:
        out, seq = [], ""
        while True:
            page = await self._plain("GET", c.WEBVIEW_HOST + path, params=dict(params, **({"seq_id": seq} if seq else {})))
            rows = page.get("list") or []
            # pages come newest first, so the first old row means everything after it is old too
            fresh = [r for r in rows if int(r.get("seqId") or 0) > stop and int(r.get("gachaTs") or 0) >= after_ms]
            out += fresh
            if not page.get("hasMore") or not rows or len(fresh) < len(rows):
                return out
            seq = rows[-1]["seqId"]

    async def pulls(
        self,
        uid: int | str | None = None,
        *,
        since: Pulls | None = None,
        after: date | datetime | None = None,
        raw: bool = False,
    ) -> Pulls | dict:
        role = await self.role(uid)
        if since is not None and since.uid and since.uid != role.uid:
            raise ValueError(f"those pulls belong to UID {since.uid}, not {role.uid}")
        if isinstance(after, datetime):
            after_ms = int(after.timestamp() * 1000)
        elif isinstance(after, date):
            after_ms = int(datetime(after.year, after.month, after.day, tzinfo=timezone.utc).timestamp() * 1000)
        else:
            after_ms = 0
        base = {"lang": "en-us", "token": await self._gacha_token(role), "server_id": role.server_id}
        known = since.last_seq if since else {}
        pools = await self._plain("GET", c.WEBVIEW_HOST + "/api/record/weapon/pool", params=base)
        pool_ids = [p["poolId"] for p in pools] if isinstance(pools, list) else []

        operator_pages = await asyncio.gather(*(
            self._pull_pages("/api/record/char", dict(base, pool_type=f"E_CharacterGachaPoolType_{kind.title()}"),
                             known.get(kind, 0), after_ms)
            for kind in OPERATOR_BANNERS
        ))
        weapon_pages = await asyncio.gather(*(
            self._pull_pages("/api/record/weapon", dict(base, pool_id=pool), known.get(pool, 0), after_ms)
            for pool in pool_ids
        ))
        if raw:
            return {"operators": dict(zip(OPERATOR_BANNERS, operator_pages)), "weapons": dict(zip(pool_ids, weapon_pages))}

        result = Pulls(
            uid=role.uid,
            operators=list(since.operators) if since else [],
            weapons=list(since.weapons) if since else [],
            gifts=list(since.gifts) if since else [],
        )
        for kind, rows in zip(OPERATOR_BANNERS, operator_pages):
            for row in rows:
                pull = Pull.model_validate(dict(row, banner=kind))
                (result.operators if pull.kind == "draw" else result.gifts).append(pull)
        for rows in weapon_pages:
            for row in rows:
                pull = Pull.model_validate(dict(row, banner=row.get("poolType", "")))
                (result.weapons if pull.kind == "draw" else result.gifts).append(pull)
        for group in (result.operators, result.weapons, result.gifts):
            group.sort(key=lambda p: p.seq_id)
        return result

    async def news(self, *, raw: bool = False) -> list[Notice] | dict:
        params = {"lang": NEWS_LANG.get(self.lang, "en-us"), "platform": "Windows", "channel": 6, "type": 0,
                  "code": c.BULLETIN_CODE, "hideDetail": 0, "server": 3}

        async def fetch():
            return await self._plain("GET", c.GAME_HUB_HOST + "/bulletin/v2/aggregate", params=params)

        data = await self._cache.get(("news", self.lang), 600, fetch) if self.cache else await fetch()
        if raw:
            return data
        notices = [Notice.model_validate(n) for n in data.get("list") or []]
        return sorted(notices, key=lambda n: n.start_at.timestamp() if n.start_at else 0, reverse=True)

    async def wiki(self, kind: str, *, raw: bool = False) -> list[WikiItem] | dict:
        if kind not in WIKI:
            raise ValueError(f"wiki kind should be one of {sorted(WIKI)}")
        sub = str(WIKI[kind])
        data = await self._zonai("GET", "/web/v1/wiki/item/catalog", params={"typeMainId": 1, "typeSubId": sub})
        if raw:
            return data
        items = [i for top in data.get("catalog") or [] for s in top.get("typeSub") or [] if s.get("id") == sub
                 for i in s.get("items") or []]
        return [WikiItem.model_validate(i) for i in items]

    async def wiki_index(self) -> dict[str, WikiItem]:
        lists = await asyncio.gather(*(self.wiki(kind) for kind in WIKI))
        return {item.id: item for items in lists for item in items}

    async def wiki_item(self, item_id: int | str, *, raw: bool = False) -> WikiItem | dict:
        data = await self._zonai("GET", "/web/v1/wiki/item/info", params={"id": item_id})
        if raw:
            return data
        if not data.get("item"):
            raise APIError(f"no wiki entry {item_id}")
        return WikiItem.model_validate(data["item"])

    async def inventory(self, uid: int | str | None = None, *, names: bool = True, raw: bool = False) -> Inventory | dict:
        role = await self.role(uid)
        data = await self._zonai("GET", "/web/v1/game/endfield/team/user-game-data",
                                 params={"roleId": role.uid, "serverId": role.server_id}, role=role)
        data = data.get("userGameData") or {}
        if raw:
            return data
        known: dict[str, str] = {}
        if names:
            card, weapons = await asyncio.gather(self.card(role.uid), self.wiki("weapons"))
            for op in card.chars:
                known[op.id] = op.name
                for e in op.equips:
                    known[e.equip_data.id] = e.equip_data.name
                if op.tactical_item:
                    known[op.tactical_item.tactical_item_data.id] = op.tactical_item.tactical_item_data.name
            known.update({w.game_id: w.name for w in weapons if w.game_id})

        def owned(section, count_key=None):
            out = []
            for item_id, entry in (data.get(section) or {}).items():
                if entry.get("owned") is False:
                    continue
                count = int(entry.get(count_key) or 1) if count_key else 1
                out.append(Owned(id=item_id, name=known.get(item_id, ""), count=count))
            return sorted(out, key=lambda o: (not o.name, o.name, o.id))

        return Inventory(
            operators=owned("userChars"),
            weapons=owned("userWeapons"),
            gear=owned("userEquips", "ownedCount"),
            tacticals=owned("userTacticalItems", "ownedCount"),
        )

    async def attendance(self, uid: int | str | None = None, *, raw: bool = False) -> Attendance | dict:
        role = await self.role(uid)
        data = await self._zonai("GET", ATTENDANCE, role=role)
        return data if raw else Attendance.model_validate(data)

    async def check_in(self, uid: int | str | None = None, *, raw: bool = False) -> CheckIn | dict:
        role = await self.role(uid)
        try:
            data = await self._zonai("POST", ATTENDANCE, payload={}, role=role) or {}
        except APIError as exc:
            if exc.code != ALREADY_CHECKED_IN:
                raise
            # could also be a dead login, a GET tells them apart
            cred = self.cred
            await self._zonai("GET", ATTENDANCE, role=role)
            if self.cred == cred:
                raise AlreadyCheckedIn(exc.message, code=exc.code) from None
            try:
                data = await self._zonai("POST", ATTENDANCE, payload={}, role=role) or {}
            except APIError as again:
                if again.code == ALREADY_CHECKED_IN:
                    raise AlreadyCheckedIn(again.message, code=again.code) from None
                raise
        self._cache.drop(lambda key: ATTENDANCE in key[0])
        return data if raw else CheckIn.model_validate(data)

    async def enums(self, *, raw: bool = False) -> Enums | dict:
        data = await self._zonai("GET", "/web/v1/game/endfield/enums")
        return data if raw else Enums.model_validate(data)

    async def char_banners(self, *, raw: bool = False) -> list[Banner] | dict:
        data = await self._zonai("GET", "/web/v1/wiki/char-pool")
        return data if raw else [Banner.model_validate(b) for b in data.get("list") or []]

    async def weapon_banners(self, *, raw: bool = False) -> list[Banner] | dict:
        data = await self._zonai("GET", "/web/v1/wiki/weapon-pool")
        return data if raw else [Banner.model_validate(b) for b in data.get("list") or []]
