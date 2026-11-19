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
        for op in sorted(card.chars, key=lambda c: (c.rarity, c.level), reverse=True):
            print(f"{op.rarity}* {op.name} · {op.profession} · {op.element} · lv{op.level} E{op.evolve_phase} P{op.potential_level}")

            for skill in op.char_data.skills:
                print(f"    {skill.type.value:<14} {skill.name} lv{op.skill_level(skill.id)}")

            if op.weapon:
                w = op.weapon
                gem = f" · {w.gem.name}" if w.gem else ""
                print(f"    weapon  {w.name} lv{w.level} R{w.refine_level} B{w.breakthrough_level}{gem}")

            for equip in op.equips:
                suit = f" ({equip.equip_data.suit.name})" if equip.equip_data.suit else ""
                print(f"    gear    {equip.equip_data.type.value:<6} {equip.name}{suit}")

            if op.tactical_item:
                print(f"    item    {op.tactical_item.name}")
            print()


asyncio.run(main())
