"""Supabase REST backend for the sim_* tables, as the signed-in user.

One of only two sim files allowed to import non-sim ``modules.*`` (the other is
``inputs.py``). It reuses ``account_store``'s PostgREST helpers with the user's
own JWT, so row-level security (auth.uid() = user_id) applies, and it only ever
addresses ``sim_*`` tables. Imports are lazy so the package imports cleanly
without them.
"""

from __future__ import annotations

from typing import Any, Mapping

ALLOWED_TABLES = frozenset({"sim_worlds", "sim_snapshots", "sim_results"})


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

        return "&".join(f"{quote(k, safe='')}=eq.{quote(str(v), safe='')}" for k, v in (filters or {}).items())

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
            return False, "Could not reach Supabase table storage."
        if response.status_code >= 400:
            return False, f"Supabase update failed ({response.status_code}). Is docs/supabase_sim.sql applied?"
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
