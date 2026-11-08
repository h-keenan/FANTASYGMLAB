import threading
import time

from modules import auth_supabase

CONFIG = {"url": "https://x.supabase.co", "anon_key": "k"}


def _patch(monkeypatch, calls, user=None, error=""):
    monkeypatch.setattr(auth_supabase, "is_configured", lambda c: True)

    def fake(config, token):
        calls.append(token)
        time.sleep(0.05)
        return (dict(user) if user else None), error

    monkeypatch.setattr(auth_supabase, "fetch_auth_user", fake)


def test_repeat_lookups_hit_cache(monkeypatch):
    calls = []
    _patch(monkeypatch, calls, user={"id": "u1"})
    assert auth_supabase.fetch_auth_user_cached(CONFIG, "tok") == ({"id": "u1"}, "")
    assert auth_supabase.fetch_auth_user_cached(CONFIG, "tok")[0]["id"] == "u1"
    assert len(calls) == 1


def test_cached_result_is_a_copy(monkeypatch):
    calls = []
    _patch(monkeypatch, calls, user={"id": "u1"})
    first, _ = auth_supabase.fetch_auth_user_cached(CONFIG, "tok")
    first["id"] = "mutated"
    assert auth_supabase.fetch_auth_user_cached(CONFIG, "tok")[0]["id"] == "u1"


def test_failures_are_not_cached(monkeypatch):
    calls = []
    _patch(monkeypatch, calls, user=None, error="bad")
    assert auth_supabase.fetch_auth_user_cached(CONFIG, "tok") == (None, "bad")
    auth_supabase.fetch_auth_user_cached(CONFIG, "tok")
    assert len(calls) == 2


def test_expires(monkeypatch):
    calls = []
    _patch(monkeypatch, calls, user={"id": "u1"})
    monkeypatch.setattr(auth_supabase, "_AUTH_USER_CACHE_SECONDS", 0.0)
    auth_supabase.fetch_auth_user_cached(CONFIG, "tok")
    auth_supabase.fetch_auth_user_cached(CONFIG, "tok")
    assert len(calls) == 2


def test_concurrent_callers_share_one_lookup(monkeypatch):
    calls = []
    _patch(monkeypatch, calls, user={"id": "u1"})
    threads = [
        threading.Thread(target=auth_supabase.fetch_auth_user_cached, args=(CONFIG, "tok"))
        for _ in range(8)
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(calls) == 1


def test_distinct_tokens_not_shared(monkeypatch):
    calls = []
    _patch(monkeypatch, calls, user={"id": "u1"})
    auth_supabase.fetch_auth_user_cached(CONFIG, "a")
    auth_supabase.fetch_auth_user_cached(CONFIG, "b")
    assert len(calls) == 2
