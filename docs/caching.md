# Caching and logins

## Reads

A `Client` keeps successful reads in memory for a short while. A bot where ten people check the same
account within a minute sends one request instead of ten.

| Method | Kept for |
| --- | --- |
| `card()`, `character()`, `attendance()` | 1 minute |
| `monument()`, `profile()` | 5 minutes |
| `char_banners()`, `weapon_banners()` | 10 minutes |
| `enums()` | 1 hour |

- Errors are never cached.
- If the same request is already in flight, other callers wait for it instead of sending their own.
- `check_in()` clears the cached attendance, so the calendar is right straight after.
- Writes (`check_in()`), logins and `account()` always go to SKPORT.

Turn it off or reset it:

```py
client = akef.Client(token, cache=False)
client.clear_cache()
```

The cache belongs to one `Client` in one process. Keep the client around between messages to get
any use out of it.

## Enka

`akef.Enka` keeps each Enka answer for as long as Enka's own `ttl` says, usually a minute. Enka asks API
users to respect that, and asking sooner gives the same data anyway. Two calls for one UID at the same time
share one request. `Enka(cache=False)` or `enka.clear_cache()` to skip it.

The game tables behind the stat math sit on disk, see [Enka](enka.md#game-data).

## login_file

A fresh `Client` normally spends two requests logging in before it does anything. With a file it
saves the login (and the account list) after the first run and starts from there next time:

```py
client = akef.Client(token, login_file="skport_login.json")
```

| | Fresh client + `card()` |
| --- | --- |
| without `login_file` | ~1.3 s |
| with `login_file`, after the first run | ~0.6 s |

The file is only used for the token that wrote it, a different token just logs in normally. Keep it
as private as the token itself.

## When the login expires

SKPORT ends logins in two ways and the client recovers from both on its own:

- the signing key goes stale: SKPORT answers http 401
- the login itself dies, usually after a long idle: SKPORT answers 200 with code 10001

Either way the client logs in again, saves the new login to `login_file` if you gave one, and
repeats the request once. If that fails too you get `AuthError`, which means the token itself is no
good any more.

Code 10001 is also what a second check-in returns, `check_in()` tells the two apart so you don't get
`AlreadyCheckedIn` when the login had just expired.
