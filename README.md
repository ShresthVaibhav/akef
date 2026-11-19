# akef

Async Python wrapper for Arknights: Endfield. Your SKPORT account card, operators with gear, pull history,
endgame records, daily check-in and the wiki. Also public Enka profiles by UID, and final stats like the ones
on the in-game stat screen for any operator.

## Install

```
pip install akef
```

Python 3.10+. Full docs in [`docs/`](https://github.com/ShresthVaibhav/akef/blob/main/docs/README.md), a script for every feature in
[`examples/`](https://github.com/ShresthVaibhav/akef/tree/main/examples).

## Usage

```py
import asyncio
import akef


async def main():
    async with akef.Client("your account token") as client:
        card = await client.card()
        print(card.name, card.base.level, card.base.world_level)
        print(f"sanity {card.stamina.current}/{card.stamina.max}")

        for op in card.chars:
            print(op.rarity, op.name, op.level, op.weapon.name)


asyncio.run(main())
```

Login, request signing and logging back in when the session runs out, all handled for you.

## Methods

Everything comes back as a pydantic model. Fields SKPORT adds later still show up in `model_extra`. Pass
`raw=True` to any of them to get the plain API dict instead.

| Method | Gives you |
| --- | --- |
| `card(uid=None)` | profile, operators with gear, sanity, dailies, battle pass, regions, dijiang, contracts, war echoes |
| `character(who, uid=None)` | one operator or a list, by name (any case or spacing) or SKPORT id |
| `monument(uid=None)` | endgame events: stages, rules, enemies, best clear team and time, medals |
| `contract(uid=None)` | current Contingency Contract: every run with its team, all indicators with their effect text, enemies |
| `pulls(uid=None, after=None, since=None)` | whole pull history with pity per banner |
| `inventory(uid=None)` | every owned operator, weapon, gear piece and tactical, with counts |
| `attendance(uid=None)` | this month's check-in calendar and rewards |
| `check_in(uid=None)` | claims today's check-in, raises `AlreadyCheckedIn` if its done |
| `news()` | the in-game notice board |
| `wiki(kind)` / `wiki_item(id)` | SKPORT's official database |
| `wiki_index()` | every wiki item by id, for naming the materials a page links to |
| `char_banners()` / `weapon_banners()` | current banners |
| `roles()` / `role(uid=None)` | Endfield accounts on the login |
| `enums()` | game enums: professions, elements, rarities... |
| `profile()` | SKPORT user profile |
| `account()` | Gryphline account info |

`uid=None` means the default account on the login.

<details>
<summary>Housekeeping</summary>

| Method | |
| --- | --- |
| `login()` | log in now instead of on the first request |
| `refresh()` | get a new signing key, akef does this by itself when it goes stale |
| `clear_cache()` | forget cached reads |
| `close()` | close the session, or just use `async with` |
</details>

<details>
<summary>Wiki kinds and readable pages</summary>

`operators`, `weapons`, `threats`, `gear`, `facilities`, `items`, `essence`, `valuables`

```py
ops = await client.wiki("operators")
arcane = await client.wiki_item(next(o for o in ops if o.name == "Arcane").id)
print(arcane.description)

page = akef.wiki_page(arcane, await client.wiki_index())   # quote, bio, skills, talents, lore...
print(page.quote, [s.name for s in page.skills])
```

The raw page is a deep tree of blocks, `wiki_page()` turns it into plain fields so you dont dig through it.
</details>

## Enka and final stats

SKPORT only says what an operator has equipped, not the numbers on their stat screen. `akef.Enka` works them
out same way enka.network does, from Enka's public game data. We checked them against the site and the game,
they match.

```py
async with akef.Enka() as enka:
    profile = await enka.profile(4727743200)      # any public UID, no token needed
    si = profile.build("Si")
    print(si.stats.hp, si.stats.atk, si.stats.crit_rate)
```

Enka only sees the 4 operators in the showcase. With a SKPORT card you get anyone on the account:

```py
async with akef.Client(token) as client, akef.Enka() as enka:
    card = await client.card()
    build = await enka.build(card, "Arcane")
    print(build.stats.atk, build.gear[0].lines)
```

| Method | Gives you |
| --- | --- |
| `profile(uid)` | showcased operators with final stats, plus the player's profile |
| `build(card, name)` | final stats for any operator on a SKPORT card |
| `player(card)` | the whole roster as a profile |
| `update()` | pull new game tables after a patch |
| `clear_cache()` | forget cached Enka answers |

First call downloads Enka's game tables (few MB) and keeps them on disk. After a patch they refresh by
themselves when something new shows up. More in [docs/enka.md](https://github.com/ShresthVaibhav/akef/blob/main/docs/enka.md), and how the numbers got
checked in [docs/stats.md](https://github.com/ShresthVaibhav/akef/blob/main/docs/stats.md).

## Pull history

```py
pulls = await client.pulls()
for p in pulls.pity():
    print(p.name, f"{p.since_six}/{p.hard}")

pulls.save("pulls.json")                  # or pulls.csv
old = akef.Pulls.load("pulls.json")
newer = await client.pulls(since=old)     # only fetches whats new and merges it in
recent = await client.pulls(after=date(2026, 11, 1))
```

SKPORT hands out pulls 5 a page, so first full grab of a big account takes a while. Save it and pass `since=`
next time. Passing another UID's saved pulls raises a `ValueError`, so two accounts never get mixed.

`pulls.operators`, `pulls.weapons` and `pulls.gifts` hold the pulls. `pulls.banner("standard")` and
`pulls.weapon_banner(pool_id)` filter one banner, `pulls.to_csv()` and `pulls.to_json()` give the text without
saving.

<details>
<summary>How pity is counted</summary>

| Banner | Hard pity | Featured |
| --- | --- | --- |
| Limited operators | 80, shared across limited banners | 120, per banner |
| Standard | 80 | 300 |
| Beginner | 50 | |
| Weapons | 40 | 80 |

Free urgent recruitment pulls dont move pity.
</details>

## Getting a token

While signed in to [skport.com](https://www.skport.com), open
`https://web-api.skport.com/cookie_store/account_token`. You get back something like
`{"code":0,"data":{"content":"..."}}`, the `content` string is your token.

That token is a full login for your account, dont share it with anyone.

## Caching and logins

Reads stay in memory for a short while, so a bot where ten people check the same account sends one request, not
ten. If the same request is already on its way, other callers wait for it instead of sending their own.

| What | Kept for |
| --- | --- |
| `card()`, `character()`, `attendance()`, `inventory()` | 1 minute |
| `monument()`, `contract()`, `profile()` | 5 minutes |
| `Enka.profile()` | as long as Enka's own ttl says, about a minute |
| banners | 10 minutes |
| `enums()`, wiki | 1 hour |

Errors are never cached and `check_in()` clears the cached calendar.

```py
client = akef.Client(token, cache=False)                     # no cache
client.clear_cache()                                         # fresh data next call
client = akef.Client(token, login_file="skport_login.json")  # keep the login between runs
client = akef.Client(token, debug=True)                      # log every request
```

Every new `Client` logs in first, thats two requests. With `login_file` it saves the login and your account list,
so a restart only pays for what you ask. If SKPORT expires it, akef logs in again by itself and updates the file.
Keep that file private, it works like the token. Debug logs only show the path, never tokens or query strings.

## Errors

```py
try:
    card = await client.card()
except akef.AuthError:
    ...  # token is dead, get a new one
except akef.NoRoleError:
    ...  # no Endfield account on this login
except akef.AkefError as e:
    print(e.code, e.message)
```

<details>
<summary>All errors</summary>

| Error | When |
| --- | --- |
| `AkefError` | base of all of them, has `.code` and `.message` |
| `AuthError` | token rejected or expired |
| `NoRoleError` | no Endfield account bound to the login |
| `NetworkError` | couldnt reach SKPORT or Enka |
| `APIError` | SKPORT said no for some other reason |
| `AlreadyCheckedIn` | `check_in()` when today is already claimed |
| `UnknownCharacter` | `character()` or `Enka.build()` with a name that doesnt match anyone |
| `PlayerNotFound` | Enka doesnt know the UID |
| `ShowcaseEmpty` | Enka player has nothing in their showcase |
| `MissingGameData` | something from a new patch isnt in Enka's data yet |
| `GameDataError` | saved game tables are broken, `await enka.update()` |
</details>

## Examples

| Script | Shows |
| --- | --- |
| [`card.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/card.py) | the basics off your account card |
| [`operators.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/operators.py) | every operator with skills, weapon and gear |
| [`character.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/character.py) | look up operators by name |
| [`pulls.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/pulls.py) | pull history, pity, save, load, csv |
| [`monument.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/monument.py) | monument events and clear teams |
| [`contract.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/contract.py) | contract runs, teams and indicators |
| [`endgame.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/endgame.py) | contracts and war echoes off the card |
| [`inventory.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/inventory.py) | everything you own |
| [`attendance.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/attendance.py), [`check_in.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/check_in.py) | daily check-in |
| [`banners.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/banners.py) | current banners |
| [`news.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/news.py) | notice board |
| [`wiki.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/wiki.py) | the official wiki, and pages made readable |
| [`enka.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/enka.py) | a public profile by UID with final stats |
| [`final_stats.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/final_stats.py) | final stats and gear lines for your whole roster |
| [`world.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/world.py) | regions and dijiang |
| [`caching.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/caching.py) | cache, login file and debug logs |
| [`errors.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/errors.py) | catching errors |
| [`raw.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/raw.py) | plain API dicts |
| [`roles.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/roles.py), [`account.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/account.py), [`profile.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/profile.py), [`enums.py`](https://github.com/ShresthVaibhav/akef/blob/main/examples/enums.py) | account side stuff |

They read the token from `SKPORT_TOKEN` or `~/.skport_token`, except `enka.py` which only needs a UID.

## Image cards

Want all this as pictures? [akef-cards](https://github.com/ShresthVaibhav/akef-cards) draws it: operator builds,
profiles, pull history, endgame and more. akef gets the data, akef-cards only draws.

## License

MIT. Game data for the stat math comes from [Enka.Network](https://enka.network), thanks enka.
Not affiliated with Hypergryph or Gryphline.
