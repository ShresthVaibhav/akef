import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        for notice in (await client.news())[:5]:
            print(f"{notice.start_at:%d %b}  [{notice.tab}]  {notice.headline}")


asyncio.run(main())
