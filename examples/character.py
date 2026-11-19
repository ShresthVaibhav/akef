import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    names = sys.argv[1:] or ["Arcane", "Laevatain"]
    async with akef.Client(TOKEN) as client:
        for op in await client.character(names):
            weapon = op.weapon.name if op.weapon else "-"
            print(f"{op.name:<12} Lv {op.level}  E{op.evolve_phase}  P{op.potential_level}  {weapon}")

        try:
            await client.character("laevatian")
        except akef.UnknownCharacter as e:
            print(e)


asyncio.run(main())
