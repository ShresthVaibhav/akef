# Errors

Every error is an `akef.AkefError` with `message` and `code` (SKPORT's code or the http status).

| Error | When |
| --- | --- |
| `AuthError` | the token is dead or was never valid, logging in again didn't help |
| `NoRoleError` | no Endfield account is bound to the login, or the `uid` you asked for isn't one of them |
| `UnknownCharacter` | `character()` got a name or id that isn't on the account |
| `AlreadyCheckedIn` | `check_in()` when today is already claimed (a kind of `APIError`) |
| `APIError` | SKPORT answered with an error code |
| `NetworkError` | couldn't reach SKPORT or Enka, or it timed out |
| `PlayerNotFound` | Enka doesn't know the UID |
| `ShowcaseEmpty` | the Enka player has nothing in their showcase, or hid it |
| `MissingGameData` | something from a new patch isn't in Enka's tables yet (a kind of `GameDataError`) |
| `GameDataError` | the saved game tables are broken, `await enka.update()` fixes it |

```py
try:
    card = await client.card()
except akef.AuthError:
    ...  # ask the user for a new token
except akef.NoRoleError:
    ...  # nothing bound to this login
except akef.NetworkError:
    ...  # try again later
except akef.AkefError as e:
    print(e.code, e.message)
```
