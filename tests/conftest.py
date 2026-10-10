"""Opt-in deterministic data fixtures; no global production overrides."""

from hashlib import sha256
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import fakeredis
import pytest

from modules import redis_cache


@pytest.fixture(autouse=True)
def _fake_redis_for_tests():
    """Every test gets a private, flushed in-memory Redis-compatible store
    (fakeredis) instead of a real Redis server: CI has no Redis service
    container, and the three modules.redis_cache-backed single-flight
    caches plus services.mobile_api_service's rate limiter all call
    modules.redis_cache.get_redis_client() internally, so this is the one
    place that needs to swap in a test double for all of them at once.

    A fresh fakeredis.FakeServer() per test (not a module-level shared one)
    means no rate-limit counter or single-flight cache entry can ever leak
    from one test into another.

    IMPORTANT: FakeRedis() must be constructed with an explicit shared
    `server=` instance here. Without it, fakeredis silently gives each
    *connection* its own independent in-memory store (confirmed: two
    threads sharing one `fakeredis.FakeRedis()` client with no explicit
    server can each see a completely different store), which would quietly
    break every single-flight test's concurrency assertions (each thread's
    SET NX would appear to always succeed) while still importing and
    running without error — a silent correctness hole, not a crash.
    """

    fake = fakeredis.FakeRedis(server=fakeredis.FakeServer())
    redis_cache.set_redis_client_for_testing(fake)
    try:
        yield fake
    finally:
        redis_cache.reset_redis_client_for_testing()


@pytest.fixture(autouse=True)
def _reset_college_scouting_cache_for_tests():
    """modules.college_scouting's in-process prospects/reports/class-strength
    caches are module-level dicts shared across the whole test process (the
    same idiom as modules.sleeper's lru_cache-backed live-league caches).
    Without a reset, a test earlier in the run that warms the cache with its
    own fixture rows could leak stale data into a later test expecting a
    fresh Supabase fetch — not necessarily a loud failure, possibly just a
    silently wrong assertion. Reset before and after every test."""

    from modules import college_scouting

    college_scouting._reset_cache_for_tests()
    try:
        yield
    finally:
        college_scouting._reset_cache_for_tests()


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


VALUATION_AUTHORITY_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "valuation_authority"


def frozen_valuation_authority_persisted_frame():
    """Frozen two-row snapshot of data/players.db (Keenan Allen + Davante
    Adams), captured 2026-10-08.

    data/players.db is overwritten every ~6h by the players-db-refresh
    cron ("chore(data): scheduled players.db refresh"), so a test that
    pins an exact value_score/fantasycalc_value read live from it goes
    stale for reasons unrelated to the valuation logic under test — the
    same fixture-drift failure mode tests/test_trust_fixture_isolation.py
    guards against for the public player cache.

    Both players are already provider-backed/modeled rows (fantasycalc_value
    > 0, role_score and opportunity_label populated), so
    modules.rankings.apply_local_structured_valuation only runs the
    per-row-independent legs of the pipeline for them (role/opportunity,
    injury risk, composite score) — it never recomputes market_score,
    age_curve_score, or scarcity_score, which are the only values in this
    path that depend on the full position pool via VORP/replacement-level
    (modules.rankings._apply_market_valuation_context). A two-row snapshot
    therefore reproduces byte-identical output to the full table for these
    two players, confirmed empirically against the live table before this
    fixture was captured.
    """
    import sqlite3

    import pandas as pd

    with sqlite3.connect(VALUATION_AUTHORITY_FIXTURE_DIR / "players_snapshot.db") as connection:
        return pd.read_sql_query("SELECT * FROM players", connection)


def frozen_valuation_authority_sleeper_records() -> dict:
    """Frozen data/sleeper_players.json entries for the same two players,
    captured at the same snapshot moment as
    ``frozen_valuation_authority_persisted_frame``. See that function's
    docstring for why freezing just these two players' data is safe."""

    return json.loads(
        (VALUATION_AUTHORITY_FIXTURE_DIR / "sleeper_records_snapshot.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def committed_fantasycalc(monkeypatch):
    """Opt-in model tests consume cached values without refreshing shared files."""
    import pandas as pd
    from modules import rankings

    cache = Path(__file__).resolve().parents[1] / "data/fantasycalc_values.csv"
    values = pd.read_csv(cache)
    monkeypatch.setattr(rankings, "get_dynasty_values", lambda: values.copy(deep=True))
