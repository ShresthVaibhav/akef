import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()

SAVED = Path("pulls.json")


async def main():
    async with akef.Client(TOKEN) as client:
        # first run grabs everything (takes a bit, skport gives 5 pulls a page), after that only whats new
        old = akef.Pulls.load(SAVED) if SAVED.exists() else None
        pulls = await client.pulls(since=old)
        pulls.save(SAVED)
        pulls.save("pulls.csv")

        print(f"{len(pulls.operators)} operator pulls, {len(pulls.weapons)} weapon pulls")
        for p in pulls.pity():
            extra = f"  {p.banner_pulls}/{p.featured_at} on {p.banner}" if p.featured_at else ""
            print(f"{p.name:<18} {p.since_six}/{p.hard}, 6 star in {p.left} at most{extra}")

        for pull in pulls.operators:
            if pull.rarity == 6:
                print(f"  {pull.pulled_at:%d %b}  {pull.name}  ({pull.pool_name})")


asyncio.run(main())
