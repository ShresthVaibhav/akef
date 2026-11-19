import asyncio
import sys

import akef

sys.stdout.reconfigure(encoding="utf-8")

UID = sys.argv[1] if len(sys.argv) > 1 else 4727743200


async def main():
    async with akef.Enka() as enka:
        profile = await enka.profile(UID)
        print(profile.owner.name, "Lv", profile.owner.level, "-", profile.signature or "no signature")
        for build in profile.builds:
            s = build.stats
            print(f"\n{build.name} Lv {build.level}, E{build.promotion}, P{build.potential}")
            print(f"  HP {s.hp}  ATK {s.atk}  DEF {s.defense}  crit {s.crit_rate:.1%} / {s.crit_dmg:.1%}")
            if build.weapon:
                print(f"  {build.weapon.name} Lv {build.weapon.level}")
            set_name, pieces = build.gear_set
            if set_name:
                print(f"  {set_name} x{pieces}")


asyncio.run(main())
