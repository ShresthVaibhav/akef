import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        for role in await client.roles():
            mark = " (default)" if role.is_default else ""
            print(f"{role.nickname} · {role.uid} · {role.server_name} · lv{role.level}{mark}")


asyncio.run(main())
