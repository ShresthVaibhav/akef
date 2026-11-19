import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        enums = await client.enums()
        for group in enums.groups():
            values = ", ".join(tag.value for tag in enums[group])
            print(f"{group}: {values}")

        print()
        print("profession_caster ->", enums.label("profession_caster"))


asyncio.run(main())
