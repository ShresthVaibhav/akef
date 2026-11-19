import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client, akef.Enka() as enka:
        card = await client.card()
        # enka only sees the showcase, a skport card has everyone
        for op in card.chars[:5]:
            build = await enka.build(card, op)
            s = build.stats
            print(f"{build.name:<14} HP {s.hp:>6}  ATK {s.atk:>5}  {s.main_attribute} main")
            for piece in build.gear:
                lines = ", ".join(f"{l.name} {l.text}" for l in piece.lines)
                print(f"    {piece.slot:<7} DEF {piece.defense:<3} {lines}")


asyncio.run(main())
