"""Supabase REST backend for the sim_* tables, as the signed-in user.

One of only two sim files allowed to import non-sim ``modules.*`` (the other is
``inputs.py``). It reuses ``account_store``'s PostgREST helpers with the user's
own JWT, so row-level security (auth.uid() = user_id) applies, and it only ever
addresses ``sim_*`` tables. Imports are lazy so the package imports cleanly
without them.
"""

from __future__ import annotations

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
        from modules import account_store

        self._check(table)
        parts = [self._filter_query(filters)] if filters else []
        parts.append(f"select={columns}")
        if order:
            parts.append(f"order={order}")
        if limit:
            parts.append(f"limit={int(limit)}")
        return account_store.fetch_rows(
            self.config, self.access_token, table, user_id=user_id, extra_query="&".join(parts),
            timing_label="sim_select",
        )

    def upsert(self, table, row, *, on_conflict):
        from modules import account_store

        self._check(table)
        return account_store.upsert_row(
            self.config, self.access_token, table, dict(row), on_conflict=on_conflict
        )

    def update(self, table, *, user_id, filters, values):
        import requests

        from modules import auth_supabase

        self._check(table)
        if not auth_supabase.is_configured(self.config):
            return False, "Accounts are not configured."
        query = f"user_id=eq.{user_id}&{self._filter_query(filters)}"
        try:
            response = requests.patch(
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
        import requests

        from modules import auth_supabase
        from modules.sim.store import CONFLICT

        self._check(table)
        if not auth_supabase.is_configured(self.config):
            return False, "Accounts are not configured."
        try:
            response = requests.post(
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
        from modules import account_store

        self._check(table)
        query = f"user_id=eq.{user_id}&{self._filter_query(filters)}"
        return account_store.delete_rows(
            self.config, self.access_token, table, query=query, timing_label="sim_delete"
        )


def backend_for(config: dict, access_token: str) -> Any:
    return SupabaseSimBackend(config, access_token)
