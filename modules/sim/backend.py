"""Supabase REST backend for the sim_* tables, as the signed-in user.

One of only two sim files allowed to import non-sim ``modules.*`` (the other is
``inputs.py``). It reuses ``account_store``'s PostgREST helpers with the user's
own JWT, so row-level security (auth.uid() = user_id) applies, and it only ever
addresses ``sim_*`` tables. Imports are lazy so the package imports cleanly
without them.
"""

from __future__ import annotations

import threading
from typing import Any, Mapping

ALLOWED_TABLES = frozenset({
    "sim_worlds", "sim_snapshots", "sim_results",
    "sim_games", "sim_events", "sim_week_checkpoints",
})


def _pg_detail(response: Any) -> str:
    """`` pg=<SQLSTATE>: <message>`` from a PostgREST error body (no row data)."""

    try:
        body = response.json()
        code = str(body.get("code") or "")
        message = str(body.get("message") or "")[:200]
    except Exception:  # noqa: BLE001
        return ""
    return f" pg={code}: {message}" if code or message else ""


_SESSION: Any = None
_SESSION_LOCK = threading.Lock()


def _session() -> Any:
    """One keep-alive HTTP session for every sim call in this process. ``requests.get/post`` opens a new
    connection (TCP + TLS handshake) per call; a game action makes two to five calls, so reusing the pooled
    connections to Supabase removes a handshake from each of them."""

    global _SESSION
    if _SESSION is None:
        with _SESSION_LOCK:
            if _SESSION is None:
                import requests
                from requests.adapters import HTTPAdapter

                session = requests.Session()
                adapter = HTTPAdapter(pool_connections=4, pool_maxsize=16)
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                _SESSION = session
    return _SESSION


class SupabaseSimBackend:
    def __init__(self, config: dict, access_token: str) -> None:
        self.config = config
        self.access_token = access_token

    @staticmethod
    def _check(table: str) -> None:
        if table not in ALLOWED_TABLES:
            raise ValueError(f"not a sim table: {table}")

    @staticmethod
    def _filter_query(filters: Mapping[str, str] | None) -> str:
        from urllib.parse import quote

        from modules.sim.store import parse_filter

        parts = []
        for key, value in (filters or {}).items():
            op, raw = parse_filter(value)
            parts.append(f"{quote(key, safe='')}={op}.{quote(raw, safe='')}")
        return "&".join(parts)

    def select(self, table, *, user_id, filters=None, columns="*", order="", limit=0):
        from modules import account_store, auth_supabase

        self._check(table)
        if not auth_supabase.is_configured(self.config):
            return [], "Accounts are not configured."
        parts = [self._filter_query(filters)] if filters else []
        parts.append(f"select={columns}")
        if order:
            parts.append(f"order={order}")
        if limit:
            parts.append(f"limit={int(limit)}")
        query = f"user_id=eq.{account_store._safe_text(user_id)}&" + "&".join(parts)
        try:
            response = _session().get(
                auth_supabase.rest_api_url(self.config, table, query),
                headers=auth_supabase.auth_headers(self.config, self.access_token), timeout=15,
            )
        except Exception:
            return [], "Could not reach Supabase table storage."
        if response.status_code >= 400:
            return [], account_store._safe_error(response, table=table)
        try:
            payload = response.json()
        except Exception:
            payload = []
        if isinstance(payload, list):
            return payload, ""
        return ([payload] if isinstance(payload, dict) else []), ""

    def upsert(self, table, row, *, on_conflict):
        from modules import account_store, auth_supabase

        self._check(table)
        if not auth_supabase.is_configured(self.config):
            return False, "Accounts are not configured."
        payload = {key: value for key, value in dict(row).items() if value not in (None,)}
        try:
            response = _session().post(
                auth_supabase.rest_api_url(self.config, table, f"on_conflict={on_conflict}"),
                headers={**auth_supabase.auth_headers(self.config, self.access_token),
                         "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=payload, timeout=15,
            )
        except Exception:
            return False, "Could not reach Supabase table storage."
        if response.status_code >= 400:
            return False, account_store._safe_error(response, table=table)
        return True, ""

    def update(self, table, *, user_id, filters, values):
        from modules import auth_supabase

        self._check(table)
        if not auth_supabase.is_configured(self.config):
            return False, "Accounts are not configured."
        query = f"user_id=eq.{user_id}&{self._filter_query(filters)}"
        try:
            response = _session().patch(
                auth_supabase.rest_api_url(self.config, table, query),
                headers={**auth_supabase.auth_headers(self.config, self.access_token), "Prefer": "return=minimal"},
                json=dict(values),
                timeout=15,
            )
        except Exception:
            return False, "Could not reach Supabase table storage (timed out or network error)."
        if response.status_code >= 400:
            return False, f"Supabase update failed ({response.status_code}).{_pg_detail(response)}"
        return True, ""

    def insert_many(self, table, rows):
        from modules import auth_supabase
        from modules.sim.store import CONFLICT

        self._check(table)
        if not auth_supabase.is_configured(self.config):
            return False, "Accounts are not configured."
        try:
            response = _session().post(
                auth_supabase.rest_api_url(self.config, table),
                headers={**auth_supabase.auth_headers(self.config, self.access_token), "Prefer": "return=minimal"},
                json=[dict(r) for r in rows],
                timeout=20,
            )
        except (ValueError, requests.exceptions.InvalidJSONError):
            return False, "Supabase insert failed: payload is not valid JSON (NaN/inf or unserializable value)."
        except Exception:
            return False, "Could not reach Supabase table storage (timed out or network error)."
        if response.status_code == 409:
            return False, CONFLICT
        if response.status_code >= 400:
            return False, f"Supabase insert failed ({response.status_code}).{_pg_detail(response)}"
        return True, ""

    def delete(self, table, *, user_id, filters):
        from modules import account_store, auth_supabase

        self._check(table)
        if not auth_supabase.is_configured(self.config):
            return False, "Accounts are not configured."
        query = f"user_id=eq.{user_id}&{self._filter_query(filters)}"
        try:
            response = _session().delete(
                auth_supabase.rest_api_url(self.config, table, query),
                headers={**auth_supabase.auth_headers(self.config, self.access_token), "Prefer": "return=minimal"},
                timeout=8,
            )
        except Exception:
            return False, "Could not reach Supabase table storage."
        if response.status_code >= 400:
            return False, account_store._safe_error(response, table=table)
        return True, ""


def backend_for(config: dict, access_token: str) -> Any:
    return SupabaseSimBackend(config, access_token)
