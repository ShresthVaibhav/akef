# Enka and final stats

SKPORT only tells you what an operator has equipped. `akef.Enka` reads public profiles from
[Enka.Network](https://enka.network) and works out the final stats you see on the in-game stat screen,
for Enka profiles and for SKPORT cards alike. No token needed for Enka, just a UID.

```py
async with akef.Enka() as enka:
    profile = await enka.profile(4727743200)
    arcane = profile.build("Arcane")
    print(arcane.stats.atk, arcane.stats.ult_gain)
```

```py
akef.Enka(*, lang="en", data=None, cache=True)
```

| Option | |
| --- | --- |
| `lang` | language for names: `en`, `ja`, `ko`, `zh-tw`, `zh-cn`, `es`, `de`, `fr`, `id`, `pt`, `ru`, `th`, `it`, `vi` |
| `data` | your own `akef.GameData`, if you want the tables somewhere else |
| `cache` | reuse Enka's answer for as long as its `ttl` says |

## Methods

| Method | Gives you |
| --- | --- |
| `profile(uid)` | `EnkaProfile` with the showcased operators as `Build`s and the player as `Player` |
| `build(card, name)` | a `Build` for any operator on a SKPORT `Card`, with final stats |
| `player(card)` | a `Player` from a SKPORT `Card`, whole roster |
| `update()` | pull the newest game tables now |
| `clear_cache()` | forget cached Enka answers |

Enka only sees the 4 operators in the in-game showcase. For the whole roster use a SKPORT card:

```py
async with akef.Client(token) as client, akef.Enka() as enka:
    card = await client.card()
    build = await enka.build(card, "Arcane")      # name in any case, or an operator from card.chars
    build = await enka.build(card, "Arcane", stats=False)   # skip the math, stats is None
```

Both give the same `Build`, numbers and all.

## EnkaProfile

`owner`, `builds`, `signature`, `player`, `ttl` and `raw` (Enka's JSON). `profile.build(name)` finds one
operator by name or id.

## Build

```py
build.stats.atk                       # 4802
build.stats.ult_gain                  # 1.892, percentages are fractions
build.weapon.skills[0].value          # "+156"
build.weapon.essence.terms            # [EssenceTerm(name="Intellect", points=6), ...]
build.gear[1].lines                   # [GearLine(name="Will", text="+84", level=3), ...]
build.gear_set                        # ("Eternal Xiranite", 4)
```

| Field | |
| --- | --- |
| `name`, `rarity`, `element`, `profession`, `weapon_type` | the basics |
| `level`, `promotion`, `potential` | progression |
| `stats` | final stats, see [stats](stats.md) |
| `skills` | name, kind, icon, level |
| `talents` | name, kind, icon, level, unlocked |
| `weapon` | name, rarity, level, refine, breakthrough, `skills` (stat, value, level), `essence` |
| `gear` | slot, rarity, set, DEF, `lines` with the level of each stat |
| `owner` | name, uid, level, world level, region |
| `source` | `"enka"` or `"skport"` |

`build.urls()` lists every image the build points at, handy if you draw it yourself.

## Player

`name`, `uid`, `level`, `world_level`, `region`, `avatar`, `namecard`, `signature`, `days`,
`operators_owned`, `weapons_owned`, `files`, `medals` and `roster`. Each roster entry has `id`, `name`,
`rarity`, `element`, `portrait`, `level`, `potential`, `promotion`, `profession` and its weapon.

## Game data

The stat math needs Enka's public game tables. The first call downloads them (a few MB) and keeps them in
`%LOCALAPPDATA%\akef\enka`, `~/.cache/akef/enka`, or wherever `AKEF_DATA` points.

After a game patch a new operator, weapon or gear piece may not be in the saved tables yet. Then the
newest tables are pulled once and it tries again. If Enka didnt add it yet either you get
`akef.MissingGameData`. `await enka.update()` refreshes by hand.

## Errors

| Error | When |
| --- | --- |
| `PlayerNotFound` | Enka doesnt know the UID |
| `ShowcaseEmpty` | the player has no operators in their showcase, or hid them |
| `MissingGameData` | something from a new patch isnt in Enka's tables yet |
| `GameDataError` | the saved tables are broken, `update()` fixes it |
| `UnknownCharacter` | `build()` with a name thats not on the card |
| `NetworkError` | couldnt reach Enka, Enka is rate limiting, or the game is in maintenance |
