import hashlib
import hmac
import json
import time

from akef.constants import PLATFORM, VNAME


def base_headers(ts: str) -> dict[str, str]:
    # key order matters, the server hashes this exact json
    return {"platform": PLATFORM, "timestamp": ts, "dId": "", "vName": VNAME}


def sign(path: str, body: str, salt: str, ts: str | None = None) -> dict[str, str]:
    ts = ts or str(int(time.time()))
    head = json.dumps(base_headers(ts), separators=(",", ":"))
    digest = hmac.new(salt.encode(), f"{path}{body}{ts}{head}".encode(), hashlib.sha256).hexdigest()
    return {**base_headers(ts), "sign": hashlib.md5(digest.encode()).hexdigest()}
