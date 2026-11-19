import asyncio
import json
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()
OUT = Path("raw")


async def main():
    OUT.mkdir(exist_ok=True)
    async with akef.Client(TOKEN) as client:
        dumps = {
            "card": await client.card(raw=True),
            "roles": await client.roles(raw=True),
            "attendance": await client.attendance(raw=True),
            "char_banners": await client.char_banners(raw=True),
            "weapon_banners": await client.weapon_banners(raw=True),
            "enums": await client.enums(raw=True),
            "profile": await client.profile(raw=True),
        }
    for name, data in dumps.items():
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{path} · {path.stat().st_size:,} bytes")


asyncio.run(main())
