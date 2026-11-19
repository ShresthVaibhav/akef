import asyncio
import os
import sys
from pathlib import Path

import akef

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.environ.get("SKPORT_TOKEN") or (Path.home() / ".skport_token").read_text().strip()


async def main():
    async with akef.Client(TOKEN) as client:
        p = await client.profile()
        user = p.user.basic_user
        print(f"{user.nickname} · skport id {user.id}")
        print(f"joined {user.created_at:%d %b %Y} · last login {user.latest_login_at:%d %b %Y}")
        print(f"followers {p.user_rts.follow} · fans {p.user_rts.fans} · likes {p.user_rts.liked}")
        if p.user.pendant and p.user.pendant.title:
            print(f"frame {p.user.pendant.title}")


asyncio.run(main())
