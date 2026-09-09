"""Opt-in deterministic data fixtures; no global production overrides."""

from hashlib import sha256
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import pytest


@pytest.fixture
def cached_2025_stats_season(monkeypatch):
    """The committed valuation golden uses 2025 current / 2024 prior stats."""
    from modules import sleeper

    monkeypatch.setattr(sleeper, "default_player_stats_season", lambda: 2025)
    monkeypatch.setattr(sleeper, "prior_player_stats_season", lambda: 2024)


@pytest.fixture(scope="session")
def public_player_trust_fixture(tmp_path_factory):
    """Hydrate the current universe without rewriting the committed database."""
    from scripts.profile_trust_enforcement import _load_real_frame

    source = Path(__file__).resolve().parents[1] / "data" / "players.db"
    original_digest = sha256(source.read_bytes()).hexdigest()
    destination = tmp_path_factory.mktemp("trust-public-universe") / "players.db"
    shutil.copyfile(source, destination)
    with frozen_trust_inputs():
        frame, columns = _load_real_frame(str(destination))
    assert sha256(source.read_bytes()).hexdigest() == original_digest
    return frame, columns


@contextmanager
def frozen_trust_inputs():
    """Keep the real loader on committed data at the cardinality baseline date."""
    from modules import player_eligibility, rankings, sleeper, structured_player_refresh

    root = Path(__file__).resolve().parents[1]
    inventory = json.loads((root / "data/sleeper_players.json").read_text())
    current = json.loads((root / "data/sleeper_player_stats_2025.json").read_text())
    prior = json.loads((root / "data/sleeper_player_stats_2024.json").read_text())

    class FixtureDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            baseline = datetime(2026, 9, 5, tzinfo=timezone.utc)
            return baseline.astimezone(tz) if tz else baseline.replace(tzinfo=None)

    with patch.object(player_eligibility, "datetime", FixtureDateTime), patch.object(
        rankings, "get_players", side_effect=lambda **kw: deepcopy(inventory)
    ), patch.object(
        structured_player_refresh, "load_cached_players_disk",
        side_effect=lambda *a, **kw: (deepcopy(inventory), 1),
    ), patch.object(rankings, "get_season_player_stats", return_value=current), patch.object(
        rankings, "get_prior_season_player_stats", return_value=prior
    ), patch.object(sleeper, "default_player_stats_season", return_value=2025), patch.object(
        sleeper, "prior_player_stats_season", return_value=2024
    ), patch("requests.sessions.Session.request", side_effect=AssertionError("Trust fixture attempted HTTP")) as http:
        yield
        # Provider wrappers may catch exceptions; attempted HTTP must still fail.
        http.assert_not_called()


@pytest.fixture
def committed_fantasycalc(monkeypatch):
    """Opt-in model tests consume cached values without refreshing shared files."""
    import pandas as pd
    from modules import rankings

    cache = Path(__file__).resolve().parents[1] / "data/fantasycalc_values.csv"
    values = pd.read_csv(cache)
    monkeypatch.setattr(rankings, "get_dynasty_values", lambda: values.copy(deep=True))
