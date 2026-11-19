import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        card = await client.card()
        base = card.base
        print(f"{base.name}  authority {base.level}  world {base.world_level}  {base.server_name}")
        print(f"sanity {card.stamina.current}/{card.stamina.max}")
        print(f"daily {card.daily.current}/{card.daily.max}  weekly {card.weekly.score}/{card.weekly.total}")
        print(f"{len(card.chars)} operators, showing off: {', '.join(op.name for op in card.showcased)}")


asyncio.run(main())
