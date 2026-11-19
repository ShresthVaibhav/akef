import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        ops = await client.wiki("operators")
        print(f"{len(ops)} operators on the wiki")
        arcane = await client.wiki_item(next(o for o in ops if o.name == "Arcane").id)
        print(arcane.name)
        print(arcane.description)

        # the raw page is a deep tree, wiki_page makes it readable. the index names upgrade materials
        page = akef.wiki_page(arcane, await client.wiki_index())
        print()
        print(page.quote)
        for skill in page.skills:
            print(f"  {skill.kind}: {skill.name}")
        print("sections:", ", ".join(p.value for p in page.parts))


asyncio.run(main())
