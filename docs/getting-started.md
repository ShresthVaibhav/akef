# Getting started

## Install

```
pip install akef
```

Python 3.10 or newer. The only dependencies are aiohttp and pydantic.

## Get a token

While signed in to [skport.com](https://www.skport.com), open
`https://web-api.skport.com/cookie_store/account_token`. It answers with something like

```json
{"code":0,"data":{"content":"nlmdN..."}}
```

The `content` string is the token. It's a full login for that account, treat it like a password.

## First request

```py
import asyncio
import akef


async def main():
    async with akef.Client("your token") as client:
        card = await client.card()
        print(card.name, "Authority", card.base.level)
        print(f"sanity {card.stamina.current}/{card.stamina.max}")


asyncio.run(main())
```

You never call `login()` yourself. The first request logs in, and if SKPORT drops the login later
the client logs in again and repeats the request.

## In a bot

Make one `Client` per token and keep it around instead of building a new one per message. That way
the login, the account list and the [cache](caching.md) are reused:

```py
clients: dict[int, akef.Client] = {}


def client_for(user_id: int, token: str) -> akef.Client:
    if user_id not in clients:
        clients[user_id] = akef.Client(token, login_file=f"logins/{user_id}.json")
    return clients[user_id]
```

Close them when the bot shuts down with `await client.close()`.

## Several accounts on one login

A SKPORT login can have more than one Endfield account bound. Every method that reads game data
takes a `uid`; leave it out and the default account is used.

```py
for role in await client.roles():
    print(role.uid, role.nickname, role.server_name)

card = await client.card(4727743200)
```
