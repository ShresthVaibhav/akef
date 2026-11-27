from akef.signing import base_headers, sign


def test_header_order():
    assert list(base_headers("1")) == ["platform", "timestamp", "dId", "vName"]


def test_sign_is_stable():
    out = sign("/api/v1/game/player/binding", "", "0123456789abcdef0123456789abcdef", ts="1794842554")
    assert out["timestamp"] == "1794842554"
    assert out["sign"] == "4fe5e21c32a5e43d998a5e578e75adc7"


def test_query_sign():
    salt = "0123456789abcdef0123456789abcdef"
    a = sign("/api/v1/game/endfield/card/detail", "roleId=1&serverId=2", salt, ts="1")
    b = sign("/api/v1/game/endfield/card/detail", "roleId=1&serverId=3", salt, ts="1")
    assert a["sign"] != b["sign"]
