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

        for region in card.domain:
            print(f"{region.name} · lv{region.level} · money {region.money.count}/{region.money.total}")
            for s in region.settlements:
                print(f"    settlement  {s.name} lv{s.level}")
            for area in region.areas:
                p, c, b = area.puzzle_count, area.trchest_count, area.blackbox_count
                print(f"    {area.name:<24} puzzles {p.count}/{p.total} · chests {c.count}/{c.total} · black boxes {b.count}/{b.total}")
            print()

        print("dijiang")
        for room in card.space_ship.rooms:
            print(f"    room type {room.type} lv{room.level} · {len(room.chars)} operators")
        print()

        print(f"achievements {card.achieve.count}")
        for medal in card.achieve.showcased:
            print(f"    {medal.name} · {medal.achievement_data.cate_name}")


asyncio.run(main())
