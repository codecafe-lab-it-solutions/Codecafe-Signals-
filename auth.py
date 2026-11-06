"""Logins for the hosted dashboard.

Roles: "admin" creates client accounts and resets passwords; "client" can change their own password;
"demo" is the shared pitch login and cannot change its password. Accounts live in store.py under "users".
The first admin and the demo login come from env vars ADMIN_USER/ADMIN_PASSWORD and DEMO_USER/DEMO_PASSWORD.
Sessions are signed cookies (HMAC with SECRET_KEY); set SECRET_KEY in the cloud or everyone is logged out on restart.
"""
import hashlib
import hmac
import os
import re
import secrets
import time

import store

SECRET = (os.getenv("SECRET_KEY") or secrets.token_hex(32)).encode()
SESSION_DAYS = 7
NAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")
ROLES = ("admin", "client", "demo")


def _hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()


def users():
    return store.get("users", {})


def _check_password(password):
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")


def create_user(name, password, role="client"):
    name = name.strip().lower()
    if not NAME_RE.match(name):
        raise ValueError("Username must be 3-32 characters: a-z, 0-9, dot, dash or underscore.")
    if role not in ROLES:
        raise ValueError(f"Role must be one of {ROLES}.")
    _check_password(password)
    u = users()
    if name in u:
        raise ValueError(f"User {name} already exists.")
    salt = secrets.token_hex(16)
    u[name] = {"salt": salt, "hash": _hash(password, salt), "role": role, "created": time.time()}
    store.put("users", u)
    return name


def set_password(name, password):
    _check_password(password)
    u = users()
    if name not in u:
        raise ValueError(f"No user {name}.")
    salt = secrets.token_hex(16)
    u[name].update(salt=salt, hash=_hash(password, salt), changed=time.time())
    store.put("users", u)


def delete_user(name):
    u = users()
    if u.get(name, {}).get("role") == "admin" and sum(x["role"] == "admin" for x in u.values()) == 1:
        raise ValueError("Cannot delete the last admin.")
    u.pop(name, None)
    store.put("users", u)


def login(name, password):
    """Return the role if the password is right, else None."""
    u = users().get(name.strip().lower())
    if u and hmac.compare_digest(u["hash"], _hash(password, u["salt"])):
        return u["role"]
    return None


def make_token(name):
    payload = f"{name}|{int(time.time()) + SESSION_DAYS * 86400}"
    return payload + "|" + hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def read_token(token):
    """Return (name, role) for a valid, unexpired session cookie of a user who still exists, else None."""
    try:
        name, exp, sig = (token or "").split("|")
    except ValueError:
        return None
    good = hmac.new(SECRET, f"{name}|{exp}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, good) or int(exp) < time.time():
        return None
    u = users().get(name)
    return (name, u["role"]) if u else None


def bootstrap():
    """Create the first admin and the demo login from env vars if they don't exist yet."""
    for role, prefix in (("admin", "ADMIN"), ("demo", "DEMO")):
        name, pw = os.getenv(f"{prefix}_USER"), os.getenv(f"{prefix}_PASSWORD")
        if name and pw and name.strip().lower() not in users():
            create_user(name, pw, role)
