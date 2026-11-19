import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        att = await client.attendance()
        print(f"claimed {att.claimed}/{len(att.calendar)} this month")

        for i, day in enumerate(att.calendar, 1):
            reward = att.reward(day)
            state = "done" if day.done else "today" if day is att.today else ""
            print(f"    day {i:>2}  {reward.display_name} x{reward.count}  {state}")


asyncio.run(main())
