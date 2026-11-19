import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        monument = await client.monument()
        # records only carry ids, the card has the names
        names = {c.id: c.name for c in (await client.card()).chars}
        for group in monument.groups:
            normal, hard = group.cleared
            medal = f"medal lv {group.achieve.level}" if group.achieve and group.achieve.level else "no medal"
            print(f"{group.name:<34} {normal}/{len(group.dungeon_groups)} normal  {hard} agony  {medal}")
            for pair in group.dungeon_groups:
                for stage in (pair.normal_dungeon, pair.hard_dungeon):
                    record = stage and stage.best_record
                    if record:
                        team = ", ".join(names.get(c.char_id, "?") for c in record.chars)
                        print(f"    {stage.name:<38} {record.seconds}s  {record.cleared_at:%Y-%m-%d}  [{team}]")


asyncio.run(main())
