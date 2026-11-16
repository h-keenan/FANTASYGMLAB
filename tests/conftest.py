"""Opt-in deterministic data fixtures; no global production overrides."""

import os

# The season clock would otherwise call Sleeper's /state/nfl; tests use the
# deterministic calendar rule (modules.season_clock.clock_from_calendar).
os.environ.setdefault("FANTASYDESK_SEASON_CLOCK_OFFLINE", "1")

from hashlib import sha256
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import fakeredis
import pytest

from modules import redis_cache


_REPO_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
# Leaked writes to data/*.json are reverted (and surfaced as a warning) so
# they can never be committed by accident. data/sleeper_players.json is
# additionally validated: a test that leaves anything other than a real
# id -> player-record map in it fails outright, because that file breaks the
# scheduled players.db refresh.


def _data_json_stat(path: Path):
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


# Session-start baseline (per xdist worker): stat + original bytes, so a leaked
# write can be detected cheaply per test and then undone.
_DATA_BASELINE = {
    path.name: (_data_json_stat(path), path.read_bytes())
    for path in sorted(_REPO_DATA_DIR.glob("*.json"))
}


# data/players.db is committed too, and rankings.load_players() reconciles and
# WRITES BACK to the path it is given. A test that loads the real default db
# rewrites the tracked file for the rest of the run (and for other xdist
# workers), which is how tests/test_canonical_player_state_authority.py (it
# copies data/players.db) failed depending on which test ran first. Same rule
# as the JSON files, but a leak fails the test: tests must load a tmp copy
# (see tests/test_canonical_player_state_authority.py) or patch the loader.
_PLAYERS_DB = _REPO_DATA_DIR / "players.db"
_PLAYERS_DB_BASELINE = (_data_json_stat(_PLAYERS_DB), _PLAYERS_DB.read_bytes() if _PLAYERS_DB.exists() else None)


@pytest.fixture(autouse=True)
def _guard_real_players_db():
    yield
    stat, content = _PLAYERS_DB_BASELINE
    if content is None:
        return
    if _data_json_stat(_PLAYERS_DB) != stat and _PLAYERS_DB.read_bytes() != content:
        _PLAYERS_DB.write_bytes(content)
        pytest.fail(
            "test rewrote the committed data/players.db (reverted); load a tmp_path copy "
            "or patch modules.rankings.load_players instead",
            pytrace=False,
        )


# Per-process record of writes to the protected data/*.json files. Under
# pytest-xdist every worker shares the real data/ directory, so inspecting the
# file alone cannot say WHO wrote it: a leak in worker A's test was blamed on
# whichever unrelated test in worker B happened to finish while the bad file
# was on disk. An audit hook only sees this process's own writes, so the guard
# can attribute a write to the test that actually made it.
_OWN_DATA_WRITES: list[str] = []
_PROTECTED_DATA_PATHS = {str(p.resolve()) for p in _REPO_DATA_DIR.glob("*.json")}


def _audit_own_data_writes(event, args):
    try:
        if event == "open":
            target, mode = args[0], args[1]
            if mode and not any(c in str(mode) for c in "wax+"):
                return
        elif event in ("os.rename", "shutil.copyfile", "shutil.move"):
            target = args[1]
        else:
            return
        if not isinstance(target, (str, bytes, os.PathLike)):
            return
        path = os.path.abspath(os.fsdecode(target))
        if path in _PROTECTED_DATA_PATHS:
            _OWN_DATA_WRITES.append(Path(path).name)
    except Exception:
        return


sys.addaudithook(_audit_own_data_writes)


@pytest.fixture(autouse=True)
def _guard_real_data_json_files():
    """Stop tests from persisting changes into the repo's real data/*.json.

    Those files are committed, and the scheduled players.db refresh consumes
    data/sleeper_players.json, so a test that forgets to redirect a cache
    path to tmp_path silently corrupts production data once committed (PR
    #1431 shipped a test fixture as sleeper_players.json and broke the
    refresh for days). Tests should use tmp paths. This reverts any leaked
    write and fails the test if it touched a protected file.
    """
    del _OWN_DATA_WRITES[:]
    yield
    from modules.sleeper import players_map_is_valid

    own_writes = set(_OWN_DATA_WRITES)

    current = {p.name: p for p in _REPO_DATA_DIR.glob("*.json")}
    touched = []
    corrupted = []
    for name, path in current.items():
        base = _DATA_BASELINE.get(name)
        if name == "sleeper_players.json" and base is not None and name in own_writes:
            try:
                valid = players_map_is_valid(json.loads(path.read_bytes()))
            except ValueError:
                valid = False
            if not valid:
                corrupted.append(name)
        if base is None:
            # New json file created under data/ by a test: remove it.
            path.unlink(missing_ok=True)
            touched.append(name)
        elif _data_json_stat(path) != base[0] and path.read_bytes() != base[1]:
            path.write_bytes(base[1])
            touched.append(name)
    for name, (_, content) in _DATA_BASELINE.items():
        if name not in current:
            (_REPO_DATA_DIR / name).write_bytes(content)
            touched.append(name)
    assert not corrupted, (
        f"test left {corrupted} (reverted) without a valid id -> player "
        "record map; redirect the cache path to tmp_path "
        "(monkeypatch/patch.object) instead"
    )
    if touched:
        import warnings

        warnings.warn(
            f"test wrote to real repo data files {sorted(set(touched))} "
            "(reverted); use tmp_path instead",
            stacklevel=1,
        )


_FAR_FUTURE_SECONDS = 30 * 24 * 3600


def _pin_fresh(path: Path) -> None:
    """Give a copy an mtime far in the future so it is never "stale"."""
    stamp = datetime.now(timezone.utc).timestamp() + _FAR_FUTURE_SECONDS
    os.utime(path, (stamp, stamp))


@pytest.fixture(scope="session", autouse=True)
def _private_sleeper_players_cache(tmp_path_factory):
    """Point modules.sleeper at a private, never-stale copy of the dump.

    ROOT CAUSE of the intermittent "test left ['sleeper_players.json']
    without a valid id -> player record map" failures: sleeper.get_players()
    treats the dump as stale once its mtime is older than
    PLAYERS_CACHE_TTL_SECONDS (5 minutes) and then refreshes it, atomically
    replacing data/sleeper_players.json with whatever the test's mocked
    ``requests.get`` returned (a tiny fixture). In CI/fresh checkouts the
    file's mtime is the checkout time, so the suite is fine for five minutes
    and then every test that calls get_players() without redirecting the
    cache path becomes a writer; which test it is depends on timing and on
    which xdist worker runs it. Every worker shares data/, so the corrupt
    file was then blamed on unrelated tests in other workers.

    Tests now read/write a per-worker copy whose mtime is pinned in the
    future, so the real file is never refreshed or rewritten. Tests that
    deliberately exercise refresh logic already patch PLAYERS_CACHE_PATH to
    their own tmp_path and keep doing so.
    """
    from modules import sleeper

    real = _REPO_DATA_DIR / "sleeper_players.json"
    if not real.exists():
        yield None
        return
    private = tmp_path_factory.mktemp("sleeper-players-cache") / "sleeper_players.json"
    shutil.copyfile(real, private)
    _pin_fresh(private)
    original = sleeper.PLAYERS_CACHE_PATH
    sleeper.PLAYERS_CACHE_PATH = str(private)
    sleeper._players_memo = None
    try:
        yield private
    finally:
        sleeper.PLAYERS_CACHE_PATH = original
        sleeper._players_memo = None


@pytest.fixture(scope="session", autouse=True)
def _hermetic_nfl_games_cache(tmp_path_factory):
    """Keep the NFL schedule (nflverse games.csv) out of the network and out of
    git-ignored local state.

    modules.nfl_schedule fetches https://github.com/nflverse/nfldata/... when
    data/nfl_games.csv is missing or older than 6 hours. That file is
    git-ignored, so a fresh worktree (and any machine whose copy aged out)
    made unrelated tests (kickoff lookups for locked starters, team profiles)
    issue an extra HTTP request, which tests that stub ``requests.get`` rightly
    reject; machines that happened to have a fresh copy passed. Tests now use
    a private, never-stale, empty schedule (header only: "kickoff unknown").
    Tests that exercise schedule loading patch GAMES_CACHE_PATH themselves.
    """
    from modules import nfl_schedule

    private = tmp_path_factory.mktemp("nfl-games-cache") / "nfl_games.csv"
    private.write_text("game_id,season,week,gameday,gametime,away_team,home_team\n", encoding="utf-8")
    _pin_fresh(private)
    original = nfl_schedule.GAMES_CACHE_PATH
    nfl_schedule.GAMES_CACHE_PATH = str(private)
    nfl_schedule.clear_load_games_cache()
    try:
        yield private
    finally:
        nfl_schedule.GAMES_CACHE_PATH = original
        nfl_schedule.clear_load_games_cache()


@pytest.fixture(autouse=True)
def _restore_private_sleeper_players_cache(_private_sleeper_players_cache):
    """A test that rewrote the private copy must not leak into the next one."""
    private = _private_sleeper_players_cache
    if private is None:
        yield
        return
    baseline = (private.stat().st_mtime_ns, private.stat().st_size)
    yield
    try:
        current = private.stat()
        changed = (current.st_mtime_ns, current.st_size) != baseline
    except OSError:
        changed = True
    if changed:
        from modules import sleeper

        private.write_bytes(_DATA_BASELINE["sleeper_players.json"][1])
        _pin_fresh(private)
        sleeper._players_memo = None


@pytest.fixture(autouse=True)
def _fake_redis_for_tests():
    """Every test gets a private, flushed in-memory Redis-compatible store
    (fakeredis) instead of a real Redis server: CI has no Redis service
    container, and the four modules.redis_cache-backed single-flight
    caches (trade-idea records, league rankings frames/summaries, playoff
    odds, and the public-players frame) plus services.mobile_api_service's
    rate limiter all call modules.redis_cache.get_redis_client()
    internally, so this is the one place that needs to swap in a test
    double for all of them at once.

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
def _reset_derived_memos_for_tests():
    """Derived memos (modules.derived_cache) key on valued-frame tags that name a cache entry; tests reuse league ids with
    different stubbed data, so no memoised derivation may outlive its test."""
    from modules import derived_cache

    derived_cache.clear_all_memos()
    yield
    derived_cache.clear_all_memos()


@pytest.fixture(autouse=True)
def _reset_auth_user_cache_for_tests():
    """The GoTrue user memo is process-global; tests reuse tokens with
    different stubbed users, so never let one test's lookup leak to the next."""
    from modules import auth_supabase

    auth_supabase.clear_auth_user_cache()
    yield
    auth_supabase.clear_auth_user_cache()


@pytest.fixture(autouse=True)
def _reset_sleeper_budget_for_tests():
    """modules.sleeper_budget keeps process-global last-known payloads and a
    call counter; without a reset one test's successful fetch would be served
    as last-known data to a later test that expects a failure."""

    from modules import sleeper_budget, sleeper_cache

    sleeper_budget.reset_for_tests()
    sleeper_cache.reset_for_tests()
    from modules import sleeper

    with sleeper._season_stats_memo_lock:
        sleeper._season_stats_fallback.clear()
    yield
    sleeper_budget.reset_for_tests()
    sleeper_cache.reset_for_tests()


@pytest.fixture(autouse=True)
def _reset_sleeper_process_caches_for_tests():
    """modules.sleeper keeps process-level ``lru_cache``s on its live-league
    endpoints (``get_league_drafts``, ``get_draft``, users, rosters, ...) and on
    the global trending lists. Whether a test's own (mocked) Sleeper call is
    made at all then depends on which test ran earlier in the same process (or
    xdist worker): the same endpoint test passes alone and fails after another
    test warmed league "abc". Clear them around every test so each test sees a
    cold, deterministic cache, whatever ran before it."""

    from modules import sleeper

    sleeper.clear_live_league_endpoint_caches()
    sleeper.clear_trending_player_caches()
    try:
        yield
    finally:
        sleeper.clear_live_league_endpoint_caches()
        sleeper.clear_trending_player_caches()


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


@pytest.fixture(autouse=True)
def _no_real_weather_network(monkeypatch):
    """modules.game_weather would call Open-Meteo for any not-yet-played game
    in a fixture. Tests never hit the real network: weather is off unless a
    test explicitly re-enables it (and mocks requests.get)."""

    monkeypatch.setenv("FANTASYDESK_WEATHER_DISABLED", "1")
    from modules import game_weather

    game_weather.clear_cache()
    yield
    game_weather.clear_cache()
