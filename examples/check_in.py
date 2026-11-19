import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        try:
            result = await client.check_in()
        except akef.AlreadyCheckedIn:
            print("already checked in today")
            return

        for reward in result.rewards:
            print(f"got {reward.display_name} x{reward.count}")
        for reward in result.tomorrow:
            print(f"tomorrow: {reward.display_name} x{reward.count}")


asyncio.run(main())
