import asyncio
import time
from typing import Any, Awaitable, Callable


class TTLCache:
    def __init__(self):
        self._data: dict[Any, tuple[float, Any]] = {}
        self._running: dict[Any, asyncio.Future] = {}

    async def get(self, key, ttl: float | Callable[[Any], float], fetch: Callable[[], Awaitable], keep: Callable[[Any], bool] = lambda v: True):
        hit = self._data.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        running = self._running.get(key)
        if running is not None:
            return await asyncio.shield(running)
        task = asyncio.ensure_future(fetch())
        self._running[key] = task
        try:
            value = await task
        finally:
            self._running.pop(key, None)
        if keep(value):
            life = ttl(value) if callable(ttl) else ttl
            self._data[key] = (time.monotonic() + life, value)
        return value

    def drop(self, match: Callable[[Any], bool] = lambda key: True) -> None:
        for key in [k for k in self._data if match(k)]:
            del self._data[key]

    def __len__(self) -> int:
        return len(self._data)
