"""Offline checks for logins. Run: uv run python test_auth.py"""
import tempfile

import store

store.URL, store.DIR = "", tempfile.mkdtemp()  # never touch real logins

import auth  # noqa: E402

auth.create_user("Client1", "temp-pass-1")
assert auth.login("client1", "temp-pass-1") == "client"
assert auth.login("client1", "wrong-pass") is None
assert auth.login("nobody", "temp-pass-1") is None

for bad in (("ab", "long-enough"), ("ok_name", "short"), ("client1", "temp-pass-1")):
    try:
        auth.create_user(*bad)
        assert False, f"should refuse {bad}"
    except ValueError:
        pass

tok = auth.make_token("client1")
assert auth.read_token(tok) == ("client1", "client")
assert auth.read_token(tok[:-1] + ("0" if tok[-1] != "0" else "1")) is None  # tampered signature
assert auth.read_token("client1|1|abc") is None and auth.read_token("") is None

auth.set_password("client1", "new-pass-123")
assert auth.login("client1", "temp-pass-1") is None and auth.login("client1", "new-pass-123") == "client"

auth.create_user("boss", "admin-pass-1", "admin")
try:
    auth.delete_user("boss")
    assert False, "last admin must stay"
except ValueError:
    pass
auth.delete_user("client1")
assert auth.read_token(tok) is None  # deleted users lose their session
print("all auth checks passed")
