---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

<div markdown>

# akef<span>.</span>

Async Python wrapper for Arknights: Endfield. Your SKPORT account card, operators with gear, pull history,
endgame records, daily check-in and the wiki, plus Enka profiles and final stats like the in-game stat screen.

[Get started](getting-started.md){ .md-button .md-button--primary }
[Client](client.md){ .md-button }

</div>

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

</div>

```
pip install akef
```

Python 3.10+. Login, request signing and logging back in when the session dies are handled for you. Everything
comes back as a pydantic model, `raw=True` gives you SKPORT's json instead.

## What it does

<div class="grid cards" markdown>

-   :material-card-account-details: **[Account card](client.md#game-data)**

    Level, sanity, dailies, battle pass, every operator with skills, weapon, essence and gear.

-   :material-dice-multiple: **[Pull history](client.md#pull-history)**

    Every pull with pity per banner, only fetches what's new, saves to json or csv.

-   :material-trophy: **[Endgame](client.md#game-data)**

    Monument clears with teams and times, Contingency Contract runs.

-   :material-calendar-check: **[Check-in](client.md#check-in)**

    The attendance calendar and the daily check-in.

-   :material-account-search: **[Enka profiles](enka.md)**

    Anyone's showcase by UID, no login needed.

-   :material-calculator-variant: **[Final stats](stats.md)**

    HP, ATK, crit and the rest for any operator, checked against the game's stat screen.

-   :material-book-open-variant: **[Wiki](client.md#wiki)**

    The official SKPORT wiki, operator pages as plain data.

-   :material-lightning-bolt: **[Caching](caching.md)**

    Cached reads, shared requests, logins that survive restarts.

</div>

## Made with it

[akef-cards](https://shresthvaibhav.github.io/akef-cards/) draws image cards from akef's data.

![akef-cards operator card](https://raw.githubusercontent.com/ShresthVaibhav/akef-cards/main/docs/images/operator_2.jpg){ .no-zoom }

Runnable scripts for every feature are in [examples](https://github.com/ShresthVaibhav/akef/tree/main/examples), bot
recipes and a FAQ are in the [wiki](https://github.com/ShresthVaibhav/akef/wiki).
