---
hide:
  - toc
---

# akef

Async Python wrapper for Arknights: Endfield. It logs into your SKPORT account and gets your card, operators
with gear, pull history, endgame records, check-in and the wiki. It also reads Enka profiles by UID and works
out final stats that match the in-game stat screen.

```
pip install akef
```

```py
import asyncio
import akef


async def main():
    async with akef.Client("your account token") as client:
        card = await client.card()
        print(card.name, card.base.level)
        print(f"sanity {card.stamina.current}/{card.stamina.max}")

        for op in card.chars:
            print(op.rarity, op.name, op.level, op.weapon.name)


asyncio.run(main())
```

Login, request signing and logging back in when the session dies are handled for you. Everything comes back as a
pydantic model, pass `raw=True` if you'd rather have SKPORT's json.

## Where to look

- [Getting started](getting-started.md) for the token and your first request
- [Client](client.md) for every method
- [Models](models.md) for what comes back
- [Enka and final stats](enka.md) for profiles by UID and stats for any operator
- [How stats are checked](stats.md) if you want to know why the numbers are right
- [Caching and logins](caching.md) and [Errors](errors.md)

There's a script for every feature in [examples](https://github.com/ShresthVaibhav/akef/tree/main/examples).

I mostly made this for [akef-cards](https://shresthvaibhav.github.io/akef-cards/), which turns the data into
image cards:

![akef-cards operator card](https://raw.githubusercontent.com/ShresthVaibhav/akef-cards/main/docs/images/operator_2.jpg){ .no-zoom }
