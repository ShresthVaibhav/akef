# Client

```py
akef.Client(token, *, lang="en", session=None, timeout=20, login_file=None, cache=True, debug=False)
```

| Option | |
| --- | --- |
| `token` | the SKPORT account token |
| `lang` | language for names and text: `en`, `ja`, `ko` or `zh_Hant` (other codes give empty results) |
| `session` | your own `aiohttp.ClientSession`; if you pass one, `close()` leaves it open |
| `timeout` | seconds before a request gives up |
| `login_file` | keep the login between runs, see [caching](caching.md#login_file) |
| `cache` | short in-memory cache for reads, see [caching](caching.md) |
| `debug` | log every request (path, status, time) to the `akef` logger. Query strings are never logged, they can hold tokens |

Use it with `async with`, or call `await client.close()` when you're done.

Every method below takes `raw=True` to return SKPORT's untouched JSON as a dict instead of a model.

## Game data

### `card(uid=None)` -> `Card`

Everything on the SKPORT game card in one request: player info, every operator with skills,
talents, weapon and gear, sanity, daily and weekly progress, battle pass, credits, regions and
settlements, Dijiang, medals, Contingency Contract and War Echoes.

```py
card = await client.card()
arcane = card.character("arcane")
```

### `character(who, uid=None)` -> `Character` or `list[Character]`

One operator, or several, by name or by SKPORT id. Names ignore case, spaces and punctuation, so
`"last rite"`, `"LastRite"` and `"Last Rite"` all work. A list gives a list back in the same order.

```py
si = await client.character("si")
team = await client.character(["Arcane", "Perlica", "Laevatain"])
```

The first lookup by name reads the card once and remembers every operator's id, later lookups go
straight to SKPORT's single-operator endpoint. An unknown name raises `UnknownCharacter`, with a
suggestion when it's close to a real one:

```
no operator called 'laevatian' on UID 4727743200, did you mean 'Laevatain'?
```

### `monument(uid=None)` -> `IndieHard`

The endgame challenge events. Each group is an event with its stages, each stage has a normal and an
Agony version with rules, enemies, recommended level and your best clear (team, time, date).

```py
monument = await client.monument()
for event in monument.groups:
    normal, agony = event.cleared
    print(event.name, normal, agony)
```

### `contract(uid=None)` -> `ContractDetail`

The Contingency Contract running now, more than `card()` has on it. `status` is the summary, `history.records`
is every run you played (team, risk score, time, wave), `indicators` are all the risks you can pick with
`text` already filled in, and `stage.enemies` the roster. Runs only carry operator ids, the card has the names.

```py
detail = await client.contract()
best = detail.best
print(detail.status.name, best.score, best.seconds)
for ind in detail.indicators:
    print(f"+{ind.score} {ind.name}: {ind.text}")
```

## Pull history

### `pulls(uid=None, *, after=None, since=None)` -> `Pulls`

Every pull on operator and weapon banners, oldest first. Uses the same token, no extra login.

```py
pulls = await client.pulls()                          # everything the server still has
recent = await client.pulls(after=date(2026, 11, 1))  # only pulls from that day on
newer = await client.pulls(since=pulls)               # only what's new since last time, merged in
raw = await client.pulls(raw=True)                    # SKPORT's own records, grouped by banner
```

`pulls.operators`, `pulls.weapons` and `pulls.gifts` (dossiers and tokens the history also lists).
`pulls.pity()` gives the current pity for each banner type:

| Banner | 6-star at | Second counter |
| --- | --- | --- |
| limited operators | 80, shared between limited banners | 120 for the featured operator, per banner |
| standard | 80 | 300 pulls for the selector |
| beginner | 50 | |
| each weapon banner | 40 | 80 for the featured weapon |

Free pulls (Urgent Recruitment) don't count toward pity. With `after=` pity only sees the pulls it
fetched, so use the full history when the numbers matter. A full fetch takes ~15 s because SKPORT
pages five pulls at a time. Keep the result and pass it back with `since=` for quick updates.

### Exporting

```py
pulls.save("pulls.json")                      # JSON
pulls.save("pulls.csv")                       # or CSV, picked by the file extension
text = pulls.to_json()                        # or just the string, also to_csv()
pulls = akef.Pulls.load("pulls.json")         # read either one back
pulls = await client.pulls(since=pulls)       # and top it up with anything newer
pulls.save("pulls.json")
```

A saved file keeps every pull you've fetched, even if the server later stops listing old ones.
Times are written as ISO dates in UTC. CSV has one row per pull with the columns `uid, group, kind,
banner, pool_id, pool_name, name, item_id, rarity, is_free, is_new, pulled_at, seq_id`.

Pulls remember whose they are in `pulls.uid`. Passing one UID's history to `since=` while fetching
another raises `ValueError` instead of mixing the two.

## Check-in

### `attendance(uid=None)` -> `Attendance`

This month's calendar: which days are claimed and what each one gives.

### `check_in(uid=None)` -> `CheckIn`

Claims today's reward. Raises `AlreadyCheckedIn` if it was already claimed.

```py
try:
    result = await client.check_in()
    print("got", ", ".join(f"{r.name} x{r.count}" for r in result.rewards))
except akef.AlreadyCheckedIn:
    print("already done today")
```

## Inventory

### `inventory(uid=None, *, names=True)` -> `Inventory`

Everything the account owns: `operators`, `weapons`, `gear` and `tacticals`, each a list of `Owned`
with `id`, `name` and `count`.

SKPORT only sends ids here. With `names=True` (the default) akef fills in names from the card
(operators, equipped gear, tacticals) and the wiki (weapons). Gear that isn't equipped has no
public name source, so it keeps an empty `name` but always has its id and count.

```py
inv = await client.inventory()
print(len(inv.weapons), "weapons,", sum(g.count for g in inv.gear), "gear pieces")
```

## News

### `news()` -> `list[Notice]`

The in-game notice board, newest first. No login needed. Each notice has `headline`, `tab`
(`events`, `updates` or `news`), `start_at`, `image` (the banner), `text` (plain text) and `html`.
The language follows the client's `lang`.

## Wiki

### `wiki(kind)` -> `list[WikiItem]` and `wiki_item(item_id)` -> `WikiItem`

SKPORT's official database. `kind` is one of `operators`, `weapons`, `gear`, `essence`, `threats`,
`facilities`, `items`, `valuables`. Each item has `id`, `name` and `cover`, `wiki_item()` adds the full
page as `document`.

```py
weapons = await client.wiki("weapons")
page = await client.wiki_item(weapons[0].id)
```

### Operator pages as plain data

A raw wiki document is a deep tree of blocks and widgets. `akef.wiki_page()` turns an operator's page into
something you can read: quote, bio, info table, skills, talents, promotions, potentials, intel and stories.

```py
ops = await client.wiki("operators")
item = await client.wiki_item(next(o for o in ops if o.name == "Arcane").id)
page = akef.wiki_page(item, await client.wiki_index())
print(page.quote)
for skill in page.skills:
    print(skill.kind, skill.name)
```

`wiki_index()` names the materials and weapons a page links to, so upgrade costs come with names. Without
it talents, promotions and costs are left out. `page.parts` lists the sections that have something in them
(`akef.WikiPart`).

## Sanity

`card.stamina` has `current`, `max`, `full_at` and `seconds_left`. `max` is the account's own cap,
which grows with Authority level, so never assume a fixed number. `card.sanity_at(value)` tells you
when sanity reaches a value, worked out from how long the rest takes to refill:

```py
card = await client.card()
when = card.sanity_at(card.stamina.max - 40)   # 40 short of full, whatever this account's cap is
```

## Accounts

| Method | Returns |
| --- | --- |
| `roles()` | every Endfield account bound to the login |
| `role(uid=None)` | one of them, the default one when `uid` is left out |
| `profile()` | the SKPORT user profile |
| `account()` | the Gryphline account (region, masked email). The real email is never exposed |

## Game info

| Method | Returns |
| --- | --- |
| `char_banners()` | current operator banners |
| `weapon_banners()` | current weapon banners |
| `enums()` | game enums: elements, professions, rarities, weapon types... |

## Housekeeping

| Method | |
| --- | --- |
| `login()` | logs in now instead of on the first request |
| `clear_cache()` | forget cached reads |
| `close()` | close the HTTP session |
