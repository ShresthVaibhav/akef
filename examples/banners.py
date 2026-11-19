import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        role = await client.role()
        for kind, banners in (("operator", await client.char_banners()), ("weapon", await client.weapon_banners())):
            for banner in banners:
                print(f"[{kind}] {banner.name} · ends {banner.ends_at(role.server_type):%d %b %H:%M} UTC")
                for item in banner.items:
                    tag = " (rate up)" if item.featured else ""
                    print(f"    {item.stars}* {item.pic}{tag}")


asyncio.run(main())
