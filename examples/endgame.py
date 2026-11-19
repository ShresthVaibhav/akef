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

        for cc in card.crisis_contract:
            print(cc.name)
            print(f"    highest risk {cc.highest} · attempts {cc.challenge_count}")
            print(f"    weekly {cc.weekly_mission.count}/{cc.weekly_mission.total}"
                  f" · indicators {cc.indicator_mission.count}/{cc.indicator_mission.total}"
                  f" · stages {cc.stage_mission.count}/{cc.stage_mission.total}")
            print(f"    ends {cc.end_at_ts:%d %b %Y}")
        print()

        for season in card.war_echoes.seasons:
            print(f"{season.name} · {season.stars} stars")
            for week in season.weeks:
                print(f"    {week.name} · {week.stars} stars")
                for stage in week.dungeon_groups:
                    print(f"        {stage.name}: {stage.star}*")
        print()

        for group in card.indie_hard.groups:
            normal, hard = group.cleared
            print(f"{group.name} · normal {normal}/{len(group.dungeon_groups)} · hard {hard}/{len(group.dungeon_groups)}")


asyncio.run(main())
