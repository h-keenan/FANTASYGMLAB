"""Caller-controlled strings interpolated into PostgREST filters must be URL-quoted (audit M3).

A path value such as `x%26user_id=eq.<other>` is decoded by FastAPI to `x&user_id=eq.<other>`; unquoted, it became extra
filter parameters on the Supabase REST call. RLS still bounds the damage (calls use the caller's JWT), but the query a
caller selects must be the query the route intended.
"""

from __future__ import annotations

from modules import account_store

EVIL = "x&user_id=eq.00000000-0000-0000-0000-000000000000&or=(a.eq.1,b.eq.2)"


def test_pg_eq_quotes_filter_metacharacters():
    quoted = account_store.pg_eq(EVIL)
    for ch in ("&", "=", "(", ")", ",", " "):
        assert ch not in quoted
    assert account_store.pg_eq("  espn:123:2026 ") == "espn%3A123%3A2026"
    assert account_store.pg_eq(None) == ""
    assert account_store.pg_eq("plain-id_1") == "plain-id_1"


class _Capture:
    def __init__(self):
        self.urls: list[str] = []

    def __call__(self, url, *args, **kwargs):
        self.urls.append(url)

        class _Resp:
            status_code = 200
            text = "[]"

            def json(self):
                return []

        return _Resp()


CONFIG = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}


def test_push_token_unregister_query_is_quoted(monkeypatch):
    from modules import push_tokens

    cap = _Capture()
    monkeypatch.setattr(account_store.requests, "delete", cap)
    push_tokens.unregister_token(CONFIG, "jwt", user_id="u1", expo_push_token=EVIL)
    assert cap.urls, "expected a Supabase call"
    assert "&or=" not in cap.urls[0]
    assert cap.urls[0].count("user_id=eq.") == 1


def test_community_shared_trade_delete_query_is_quoted(monkeypatch):
    from modules import community_shared_trades

    cap = _Capture()
    monkeypatch.setattr(community_shared_trades.requests, "delete", cap)
    try:
        community_shared_trades.delete_share(CONFIG, "jwt", EVIL, "u1")
    except Exception:
        pass
    assert cap.urls
    assert "&or=" not in cap.urls[0]
    assert cap.urls[0].count("user_id=eq.") == 1


def test_route_level_filters_use_the_quoting_helper():
    """Static guard: no route-reachable `=eq.{<caller value>}` may be interpolated unquoted."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    risky = re.compile(r"=eq\.\{(outcome_id|emoji|league_id|league_key|prospect_id|pid|trade_id)\}")
    offenders = []
    for rel in (
        "services/mobile_api_service.py",
        "modules/gm_targets.py",
        "modules/decision_memory.py",
        "modules/team_stance.py",
        "modules/push_tokens.py",
        "modules/community_shared_trades.py",
    ):
        for number, line in enumerate((root / rel).read_text().splitlines(), 1):
            if risky.search(line):
                offenders.append(f"{rel}:{number}")
    assert offenders == []
