"""Guest Sleeper import must work unsigned and stay isolated from account state."""

from __future__ import annotations

from unittest.mock import patch

from modules import auth_supabase
from modules.sleeper_leagues import LeagueLookupResult, log_league_import_diagnostic


class _Session(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def test_league_import_diagnostic_omits_username(capsys):
    log_league_import_diagnostic(
        stage="username_lookup",
        status="ok",
        league_count=2,
        seasons_scanned=2,
    )
    logged = capsys.readouterr().out
    assert "DYNASTYGM_LEAGUE_IMPORT" in logged
    assert "guest_league_import" in logged
    assert "password" not in logged.casefold()
    assert "@" not in logged
