import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        detail = await client.contract()
        names = {op.char_data.id: op.name for op in (await client.card()).chars}
        print(detail.status.name, " best risk", detail.status.highest)

        for run in sorted(detail.history.records, key=lambda r: -r.score):
            team = ", ".join(names.get(c.char_id, "?") for c in run.chars)
            print(f"  risk {run.score:>2}  {run.seconds // 60}:{run.seconds % 60:02d}  wave {run.waves}  {team}")

        print("indicators you can pick:")
        for ind in sorted(detail.indicators, key=lambda i: -i.score)[:8]:
            print(f"  +{ind.score} {ind.name}: {ind.text}")


asyncio.run(main())
