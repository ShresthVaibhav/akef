import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()
logging.basicConfig(level=logging.INFO, format="%(message)s")


async def timed(label, call):
    start = time.perf_counter()
    await call
    print(f"{label}: {(time.perf_counter() - start) * 1000:.0f}ms")


async def main():
    # login_file keeps the login between runs so a restart skips it, debug logs every request (path only, no tokens)
    async with akef.Client(TOKEN, login_file="skport_login.json", debug=True) as client:
        await timed("first card", client.card())
        await timed("second card, from cache", client.card())
        await timed("five at once, one request", asyncio.gather(*(client.card() for _ in range(5))))

        client.clear_cache()
        await timed("after clear_cache", client.card())

    async with akef.Client(TOKEN, cache=False) as client:
        await timed("cache off", client.card())
        await timed("cache off again", client.card())


asyncio.run(main())
