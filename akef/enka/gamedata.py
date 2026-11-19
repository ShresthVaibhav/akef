from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

import aiohttp

from akef.errors import GameDataError, NetworkError

RAW = "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/{}"
STORE = ("avatars", "weapons", "weapon_meta", "skills", "equips", "gems", "locs", "pfps", "namecards", "medals")
SLOTS = ("body", "hand", "edc")


def default_path() -> Path:
    if os.environ.get("AKEF_DATA"):
        return Path(os.environ["AKEF_DATA"])
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(root) / "akef" / "enka"


def slot_of(icon: str) -> str:
    return next((s for s in SLOTS if f"_{s}_" in icon), "")


# enka keeps names in two places with different language codes: locs.json and the tooltip folders
LANGS = {
    "en": ("en", "EN"), "ja": ("ja", "JP"), "ko": ("ko", "KR"), "zh-tw": ("zh-tw", "CHT"), "zh-cn": ("zh-cn", "CHS"),
    "es": ("es", "ES"), "de": ("de", "DE"), "fr": ("fr", "FR"), "id": ("id", "ID"), "pt": ("pt", "PT"),
    "ru": ("ru", "RU"), "th": ("th", "TH"), "it": ("it", "IT"), "vi": ("vi", "VI"),
}
ALIASES = {"jp": "ja", "kr": "ko", "cht": "zh-tw", "zh_hant": "zh-tw", "chs": "zh-cn", "zh_hans": "zh-cn"}


def language(lang: str) -> tuple[str, str]:
    key = lang.strip().lower().replace("_", "-")
    key = ALIASES.get(key, ALIASES.get(key.replace("-", "_"), key))
    if key not in LANGS:
        raise ValueError(f"unsupported language {lang!r}, pick one of {sorted(LANGS)}")
    return LANGS[key]


class GameData:
    def __init__(self, path: str | Path | None = None, *, lang: str = "en", timeout: float = 30):
        self.path = Path(path) if path else default_path()
        self.locale, self.lang = language(lang)
        self.updated_at: float | None = None
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._lock = asyncio.Lock()
        self._tables: dict[str, dict] = {}
        self._tips: dict[tuple[str, str], dict | None] = {}
        self._refreshed = False

    @property
    def loaded(self) -> bool:
        return bool(self._tables)

    def _store_file(self, name: str) -> Path:
        return self.path / f"{name}.json"

    def _tip_file(self, kind: str, key: str) -> Path:
        return self.path / "tooltips" / self.lang / kind / f"{key}.json"

    async def load(self) -> "GameData":
        async with self._lock:
            if self.loaded:
                return self
            if not all(self._store_file(n).exists() for n in STORE):
                await self._download_store()
            self._read()
        return self

    async def update(self) -> bool:
        async with self._lock:
            changed = await self._download_store()
            self._read()
            self._tips.clear()
            tips = self.path / "tooltips"
            if tips.exists():
                for file in tips.rglob("*.json"):
                    file.unlink()
            self._refreshed = True
            return changed

    async def refresh_if_stale(self) -> bool:
        if self._refreshed:
            return False
        return await self.update()

    async def _fetch(self, session: aiohttp.ClientSession, path: str) -> bytes | None:
        async with session.get(RAW.format(path)) as resp:
            if resp.status == 404:
                return None
            if resp.status != 200:
                raise GameDataError(f"couldn't fetch {path} from Enka (http {resp.status})")
            return await resp.read()

    def _session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(timeout=self._timeout, headers={"User-Agent": "akef-cards"})

    async def _download_store(self) -> bool:
        blobs = {}
        try:
            async with self._session() as session:
                async def one(name):
                    blob = await self._fetch(session, f"store/ef/{name}.json")
                    if blob is None:
                        raise GameDataError(f"Enka has no store/ef/{name}.json")
                    blobs[name] = blob

                await asyncio.gather(*(one(n) for n in STORE))
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise NetworkError(f"couldn't reach Enka's data: {exc.__class__.__name__}") from exc

        self.path.mkdir(parents=True, exist_ok=True)
        changed = False
        for name, blob in blobs.items():
            target = self._store_file(name)
            if target.exists() and hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(blob).digest():
                continue
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(blob)
            tmp.replace(target)
            changed = True
        self.updated_at = time.time()
        (self.path / "meta.json").write_text(json.dumps({"updated_at": self.updated_at}), encoding="utf-8")
        return changed

    def _read(self) -> None:
        tables = {}
        for name in STORE:
            try:
                tables[name] = json.loads(self._store_file(name).read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                raise GameDataError(f"{name}.json in {self.path} is unreadable, run update()") from exc
        self._tables = tables
        meta = self.path / "meta.json"
        if meta.exists():
            self.updated_at = json.loads(meta.read_text(encoding="utf-8")).get("updated_at")

        self.names = tables["locs"].get(self.locale) or tables["locs"].get("en", {})
        self.avatars = tables["avatars"]
        self.weapons = tables["weapons"]
        self.skills = tables["skills"]
        self.items = tables["equips"]["Items"]
        self.suits = tables["equips"]["Suits"]
        self.gem_terms = tables["gems"]["TermNums"]
        self.gem_items = tables["gems"].get("TemplateItems", {})
        self.curves = tables["weapon_meta"]["LevelCurves"]
        self.break_bounds = tables["weapon_meta"]["BreakSkillLevelBounds"]
        self.refine_bounds = tables["weapon_meta"]["TalentSkillLevelBounds"]
        self.pfps = tables["pfps"]
        self.namecards = tables["namecards"]
        self.medals = tables["medals"]

        self.avatar_by_str = {a["StrId"]: (key, a) for key, a in self.avatars.items()}
        # skport sends names in whatever language its client uses, so match them against every language
        self.weapon_by_name, self.suit_by_name = {}, {}
        for names in tables["locs"].values():
            for key, w in self.weapons.items():
                if names.get(str(w["NameHash"])):
                    self.weapon_by_name.setdefault(names[str(w["NameHash"])], (key, w))
            for sid, s in self.suits.items():
                if names.get(str(s["NameHash"])):
                    self.suit_by_name.setdefault(names[str(s["NameHash"])], sid)
        self.items_by_group: dict[tuple, list[dict]] = {}
        for item in self.items.values():
            self.items_by_group.setdefault((item["SuitId"], slot_of(item["Icon"]), item["Rarity"]), []).append(item)

    def name(self, hash_) -> str:
        return self.names.get(str(hash_), "")

    async def tooltip(self, kind: str, key) -> dict | None:
        key = str(key)
        cached = self._tips.get((kind, key), ...)
        if cached is not ...:
            return cached
        file = self._tip_file(kind, key)
        if file.exists():
            tip = json.loads(file.read_text(encoding="utf-8-sig"))
        else:
            try:
                async with self._session() as session:
                    blob = await self._fetch(session, f"tooltip-data/ef/{self.lang}/{kind}/{key}.json")
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return None
            tip = json.loads(blob) if blob else None
            if tip is not None:
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(blob)
        self._tips[(kind, key)] = tip
        return tip
