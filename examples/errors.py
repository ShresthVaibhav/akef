import asyncio
import sys

import akef

sys.stdout.reconfigure(encoding="utf-8")


async def main():
    async with akef.Client("not-a-real-token") as client:
        try:
            await client.card()
        except akef.AuthError as e:
            print(f"token rejected: {e.message}")
        except akef.NoRoleError:
            print("no Endfield account on this login")
        except akef.NetworkError as e:
            print(f"couldn't reach skport: {e.message}")
        except akef.AkefError as e:
            print(f"api said no: {e.code} {e.message}")


asyncio.run(main())
