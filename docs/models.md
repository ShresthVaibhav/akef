# Models

Everything returned is a pydantic model with snake_case fields. SKPORT sends numbers as strings and
times as unix seconds, both come back as proper `int`s and timezone-aware `datetime`s. Fields
SKPORT adds later than this library still show up in `model_extra`.

## Card

| Field | |
| --- | --- |
| `base` | name, uid, level (Authority), world level, server, avatar, owned counts, account creation time |
| `chars` | every operator, see `Character` below |
| `stamina` | sanity: `current`, `max`, `full_at`, `seconds_left`, `is_full` |
| `daily`, `weekly` | daily activity and weekly routine progress |
| `battle_pass` | `cur_level`, `max_level` |
| `credit` | credits `count`/`total`, `has_today`, `next_refresh_ts` |
| `domain` | regions with level, funds, settlements and exploration per area |
| `space_ship` | Dijiang rooms and who's assigned |
| `achieve` | medals, `showcased` gives the ones picked for the profile in order |
| `crisis_contract` | Contingency Contract: best score, weekly/stage progress, dates |
| `war_echoes` | seasons, weeks and stars per stage |
| `config` | profile settings, `showcased` gives the operators picked for the profile |

Shortcuts: `card.name`, `card.uid`, `card.character(name_or_id)`, `card.showcased`,
`card.base.awakening_days`.

## Character

| | |
| --- | --- |
| `name`, `rarity`, `element`, `profession` | the basics |
| `level`, `evolve_phase`, `potential_level` | progression |
| `char_data` | static info: skills, art urls (`avatar_sq_url`, `avatar_rt_url`, `illustration_url`) |
| `weapon` | name, level, refine, breakthrough, skills, essence (`gem`) |
| `equips` | the gear that's equipped, in slot order |
| `tactical_item` | equipped tactical |
| `skill_level(skill_id)` | level of one skill |
| `talents`, `talent_unlocked(id)`, `unlocked_talents` | talent nodes, with the lower tiers of a line counted as unlocked |

## IndieHard (monument)

`groups` is a list of events. On an event: `name`, `pic`, `dungeon_groups` (pairs of
`normal_dungeon`/`hard_dungeon`), `achieve` (the medal), `is_in_activity`, and `cleared` which
gives `(normal, agony)` counts.

On a stage (`Dungeon`): `name`, `is_pass`, `recommend_level`, `enemies`, `rules` (the mechanics as
plain text) and `best_record` with `chars`, `cleared_at` and `seconds`.

## Attendance and CheckIn

`Attendance.calendar` is the month, `claimed` counts the claimed days, `has_today` says whether
today is done. `CheckIn.rewards` and `CheckIn.tomorrow` are lists with `name`, `count` and `icon`.

## Raw data

Anything not covered here is still in the raw JSON:

```py
data = await client.card(raw=True)
```
