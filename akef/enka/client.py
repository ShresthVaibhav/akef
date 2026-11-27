from akef.cache import TTLCache
from akef.enka.build import Build
from akef.enka.gamedata import GameData
from akef.enka.player import Player
from akef.enka.profile import EnkaProfile, fetch_player, profile_from_enka
from akef.enka.skport import build_from_skport, player_from_skport
from akef.errors import MissingGameData, UnknownCharacter


class Enka:
    def __init__(self, *, lang: str = "en", data: GameData | None = None, cache: bool = True):
        self.data = data or GameData(lang=lang)
        self.cache = cache
        self._players = TTLCache()

    async def __aenter__(self) -> "Enka":
        await self.data.load()
        return self

    async def __aexit__(self, *exc) -> None:
        pass

    def clear_cache(self) -> None:
        self._players.drop()

    async def update(self) -> bool:
        return await self.data.update()

    async def _with_refresh(self, work):
        await self.data.load()
        try:
            return await work()
        except MissingGameData:
            # new operator/weapon/gear after a patch: grab enka's latest once and try again
            if not await self.data.refresh_if_stale():
                raise
            return await work()

    async def profile(self, uid: int | str) -> EnkaProfile:
        if self.cache:
            # enka's own ttl, asking sooner returns the same data
            raw = await self._players.get(str(uid), lambda r: r.get("ttl") or 60, lambda: fetch_player(uid))
        else:
            raw = await fetch_player(uid)
        return await self._with_refresh(lambda: profile_from_enka(self.data, raw))

    async def build(self, card, character, *, stats: bool = True) -> Build:
        op = card.character(character) if isinstance(character, str) else character
        if op is None:
            raise UnknownCharacter(f"{character!r} isn't on this account")

        async def work():
            return build_from_skport(self.data, card, op, stats=stats)

        return await self._with_refresh(work)

    def player(self, card) -> Player:
        return player_from_skport(card)
