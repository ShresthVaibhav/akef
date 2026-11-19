import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        inv = await client.inventory()
        print(f"{len(inv.operators)} operators, {len(inv.weapons)} weapons, {len(inv.gear)} gear, {len(inv.tacticals)} tacticals")
        for w in inv.weapons[:10]:
            print(f"  {w.name or w.id}  x{w.count}")


asyncio.run(main())
