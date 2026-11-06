"""Tiny key-value store for data that must survive a cloud restart: user logins and paper accounts.

Uses Postgres (e.g. a free Supabase database) when DATABASE_URL is set; otherwise JSON files in ./data.
Values are plain JSON (dicts/lists). Keys look like "users" or "paper:alice".
"""
import json
import os
import re

import config  # noqa: F401  loads .env so DATABASE_URL is visible

URL = os.getenv("DATABASE_URL", "")
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _pg():
    import psycopg
    return psycopg.connect(URL, autocommit=True)


def init():
    if URL:
        with _pg() as c:
            c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v JSONB NOT NULL)")


def _path(key):
    return os.path.join(DIR, re.sub(r"[^a-z0-9_.-]", "_", key.lower()) + ".json")


def get(key, default=None):
    if URL:
        with _pg() as c:
            row = c.execute("SELECT v FROM kv WHERE k = %s", (key,)).fetchone()
        return row[0] if row else default
    try:
        with open(_path(key)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def put(key, value):
    if URL:
        from psycopg.types.json import Jsonb
        with _pg() as c:
            c.execute("INSERT INTO kv (k, v) VALUES (%s, %s) ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v",
                      (key, Jsonb(value)))
        return
    os.makedirs(DIR, exist_ok=True)
    tmp = _path(key) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(value, f, indent=2)
    os.replace(tmp, _path(key))  # atomic, so a crash never leaves half a file


init()
