"""Fantasy Sim isolation: the hard rule, enforced.

Nothing the sim does may affect real logic, and real logic never depends on
the sim. These tests are deterministic (no players.db goldens) so they can gate
every PR:

1. AST import graph: only the service's one guarded mount imports modules.sim.
2. The sim package imports only what its per-file allowlist says.
3. The engine is pure: importing it loads no real module.
4. Running the sim leaves every real data file and real endpoint output as-is.
5. The sim is off by default and registers no routes.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SIM_DIR = REPO / "modules" / "sim"
SKIP_DIRS = {".git", "node_modules", ".claude", "web-next", "mobile", "artifacts", "__pycache__"}
STDLIB = set(sys.stdlib_module_names) | {"__future__"}

# Per sim file: third-party roots allowed, and which `modules.X` it may import
# (X is checked for `from modules import X` and `import modules.X`).
THIRD_PARTY = {"numpy"}
FILE_EXTRA_THIRD_PARTY = {
    "api.py": {"fastapi", "pydantic"},
    "game_api.py": {"fastapi", "pydantic"},
    "backend.py": {"requests"},
}
FILE_REAL_MODULES = {
    "inputs.py": {"sleeper", "player_projections", "playoff_simulator"},
    "backend.py": {"account_store", "auth_supabase"},
}
# The only files outside modules/sim that may mention modules.sim, and how.
EXTERNAL_IMPORTERS = {"services/mobile_api_service.py": {"modules.sim.api"}}
PURE_ENGINE_FILES = [
    "engine.py", "analysis.py", "lineup.py", "personas.py", "rng.py", "types.py", "synthetic.py",
    "store.py", "version.py", "__init__.py", "picks.py", "player_model.py", "player_model_v1.py", "forecast.py",
    # the interactive GM game (everything but its router is pure stdlib + numpy + modules.sim)
    "game_types.py", "game_scoring.py", "game_setup.py", "game_state.py", "game_eval.py", "game_draft.py",
    "game_ai.py", "game_actions.py", "game_engine.py", "game_result.py", "game_store.py", "game_view.py", "game_home.py",
    # dynasty mode: age curves, rookie classes, the offseason and its views
    "aging.py", "game_dynasty.py", "game_dynasty_view.py",
]
CALIBRATION_DIR = SIM_DIR / "calibration"


def _py_files(root: Path):
    for path in root.rglob("*.py"):
        if SKIP_DIRS & set(path.relative_to(REPO).parts):
            continue
        if any(part.startswith(".venv") for part in path.relative_to(REPO).parts):
            continue
        yield path


def _imports(path: Path) -> list[tuple[str, tuple[str, ...], int]]:
    """(module, imported names, level) for every import in the file, at any depth."""

    out = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            out.extend((a.name, (), 0) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            out.append((node.module or "", tuple(a.name for a in node.names), node.level))
    return out


# ---------------------------------------------------------------- 1. nothing imports sim


def test_only_the_service_mount_imports_modules_sim():
    offenders = []
    for path in _py_files(REPO):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith("modules/sim/") or re.match(r"tests/test_sim_[a-z_]+\.py$", rel):
            continue
        text = path.read_text()
        if "modules.sim" not in text and "modules/sim" not in text and "from modules import sim" not in text:
            continue
        allowed = EXTERNAL_IMPORTERS.get(rel)
        if allowed is None:
            offenders.append(rel)
            continue
        for module, names, _ in _imports(path):
            targets = {module} | {f"{module}.{n}" for n in names}
            hits = {t for t in targets if t == "modules.sim" or t.startswith("modules.sim.")}
            # `from modules.sim import api` -> modules.sim.api ; bare `modules.sim` is not allowed
            hits = {h for h in hits if h != "modules.sim" or not names}
            if hits - allowed:
                offenders.append(f"{rel}: {sorted(hits - allowed)}")
    assert not offenders, f"real code must not depend on modules.sim: {offenders}"


def _service_guard_range() -> tuple[int, int]:
    lines = (REPO / "services" / "mobile_api_service.py").read_text().splitlines()
    guard = next(i for i, l in enumerate(lines) if l.startswith('if os.environ.get("SIM_ENABLED"'))
    end = next(i for i in range(guard + 1, len(lines)) if lines[i] and not lines[i].startswith((" ", ")")))
    return guard, end


def test_service_references_the_sim_only_inside_the_flag_guard():
    lines = (REPO / "services" / "mobile_api_service.py").read_text().splitlines()
    guard, end = _service_guard_range()
    mentions = [i for i, l in enumerate(lines) if "sim_api" in l or "modules.sim" in l]
    assert mentions and all(guard <= i < end for i in mentions)
    assert end - guard <= 20, "keep the mount tiny"


def test_no_sim_branches_in_real_code():
    """Real code has no sim-aware branches beyond the one guarded mount (grep guard)."""

    pattern = re.compile(r"\bis_sim\b|\bsim_mode\b|\bsimulat(?:ed|ion)_world\b|\bsim_worlds\b|SIM_ENABLED")
    guard, end = _service_guard_range()
    offenders = []
    for path in _py_files(REPO):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith("modules/sim/") or rel.startswith("tests/"):
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                in_mount = rel == "services/mobile_api_service.py" and guard - 3 <= lineno - 1 < end
                if not in_mount:
                    offenders.append(f"{rel}:{lineno}")
    assert offenders == []


# ---------------------------------------------------------------- 2. sim import allowlist


@pytest.mark.parametrize("path", sorted(SIM_DIR.glob("*.py")), ids=lambda p: p.name)
def test_sim_files_import_only_allowlisted_modules(path):
    extra = FILE_EXTRA_THIRD_PARTY.get(path.name, set())
    real_ok = FILE_REAL_MODULES.get(path.name, set())
    bad = []
    for module, names, level in _imports(path):
        if level:
            bad.append(f"relative import {module!r}")
            continue
        root = module.split(".")[0]
        if root in STDLIB or root in THIRD_PARTY or root in extra:
            continue
        if module == "modules.sim" or module.startswith("modules.sim."):
            continue
        if module == "modules":
            for n in names:
                if n == "sim":
                    continue
                if n not in real_ok:
                    bad.append(f"from modules import {n}")
            continue
        if module.startswith("modules.") and module.split(".")[1] in real_ok:
            continue
        bad.append(module)
    assert not bad, f"{path.name} imports outside its allowlist: {bad}"


def test_player_model_and_calibration_are_pure_engine_files():
    """The player outcome model and its calibration harness import only stdlib, numpy
    and modules.sim.* (no real module, no pandas, no network client)."""

    for name in PURE_ENGINE_FILES:
        assert (SIM_DIR / name).exists(), name
    assert "player_model.py" in PURE_ENGINE_FILES
    files = sorted(CALIBRATION_DIR.glob("*.py")) + [SIM_DIR / "player_model.py", SIM_DIR / "player_model_v1.py"]
    assert {f.name for f in files} >= {"player_model.py", "dataset.py", "backtest.py", "fit.py", "age_curve.py"}
    for path in files:
        bad = []
        for module, names, level in _imports(path):
            root = module.split(".")[0]
            if level or not (root in STDLIB or root in THIRD_PARTY or module.startswith("modules.sim")):
                bad.append(module or f"relative:{names}")
            if module == "modules":
                bad.append(f"from modules import {names}")
        assert not bad, f"{path.name}: {bad}"


def test_only_adapter_files_touch_real_modules():
    touching = set()
    for path in SIM_DIR.glob("*.py"):
        for module, names, _ in _imports(path):
            if module == "modules" and any(n != "sim" for n in names):
                touching.add(path.name)
            if module.startswith("modules.") and not module.startswith("modules.sim"):
                touching.add(path.name)
    assert touching == {"inputs.py", "backend.py"}


def test_sim_never_uses_streamlit_or_the_players_loaders_or_write_modes():
    forbidden = re.compile(
        r"streamlit|load_players|build_players_table|refresh_players|import app\b|"
        r"mode=rw|mode=rwc|to_sql|executescript|\binsert into players|\bupdate players|\bdelete from players"
    )
    for path in SIM_DIR.glob("*.py"):
        text = path.read_text()
        # docstrings/comments may mention the names to forbid them
        code = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )
        stripped = re.sub(r'""".*?"""', "", code, flags=re.S)
        assert not forbidden.search(stripped), f"{path.name}: {forbidden.search(stripped).group(0)}"


def test_sim_only_addresses_sim_tables():
    from modules.sim import backend, game_store, store

    world_tables = {store.WORLDS, store.SNAPSHOTS, store.RESULTS}
    game_tables = {game_store.GAMES, game_store.EVENTS, game_store.CHECKPOINTS}
    assert world_tables == {"sim_worlds", "sim_snapshots", "sim_results"}
    assert game_tables == {"sim_games", "sim_events", "sim_week_checkpoints"}
    assert backend.ALLOWED_TABLES == world_tables | game_tables
    for name, tables in (("supabase_sim.sql", world_tables), ("supabase_sim_game.sql", game_tables)):
        sql = (REPO / "docs" / name).read_text().lower()
        assert set(re.findall(r"create table if not exists public\.(\w+)", sql)) == tables
        # no foreign keys into real tables: every `references public.X` is a sim table
        assert set(re.findall(r"references public\.(\w+)", sql)) <= tables | world_tables | game_tables
        assert set(re.findall(r"references (?!public\.)(\S+?)[ (]", sql)) <= {"auth.users"}
    # every statement in the game SQL is re-runnable
    game_sql = (REPO / "docs" / "supabase_sim_game.sql").read_text().lower()
    assert "drop table" not in game_sql and "truncate" not in game_sql
    for stmt in re.findall(r"create (?:table|index) (?!if not exists)(\S+)", game_sql):
        pytest.fail(f"non-idempotent create: {stmt}")


# ---------------------------------------------------------------- 3. engine purity


def test_importing_the_engine_loads_no_real_module():
    code = (
        f"import sys, json; sys.path.insert(0, {str(REPO)!r})\n"
        "import modules.sim.engine, modules.sim.analysis, modules.sim.store, modules.sim.synthetic\n"
        + "".join(f"import modules.sim.{f[:-3]}\n" for f in PURE_ENGINE_FILES if f != "__init__.py")
        + "import modules.sim.calibration.dataset, modules.sim.calibration.backtest\n"
        "real = sorted(m for m in sys.modules if m.startswith('modules.') and not m.startswith('modules.sim'))\n"
        "print(json.dumps({'real': real, 'streamlit': 'streamlit' in sys.modules, 'pandas': 'pandas' in sys.modules}))\n"
    )
    proc = subprocess.run([sys.executable, "-I", "-c", code], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data == {"real": [], "streamlit": False, "pandas": False}


# ---------------------------------------------------------------- 4. real state unchanged


_WRITE_EVENTS = {"os.remove", "os.rename", "os.rmdir", "os.mkdir", "shutil.copyfile", "shutil.move"}
_audit_state = {"active": False, "writes": []}


def _audit_hook(event, args):
    """Record writes made by THIS process under data/. A before/after mtime
    fingerprint of the shared data dir is racy under `pytest -n auto`, because
    other xdist workers legitimately refresh data/ caches while this test runs.
    Workers are separate processes, so an in-process audit hook sees only the
    sim's own writes."""
    if not _audit_state["active"]:
        return
    try:
        if event == "open":
            path, mode, flags = args[0], args[1], args[2]
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC)
            )
            if writing and path is not None:
                _audit_state["writes"].append(os.fspath(path))
        elif event in _WRITE_EVENTS:
            _audit_state["writes"].extend(os.fspath(a) for a in args if isinstance(a, (str, bytes, os.PathLike)))
    except Exception:
        pass


sys.addaudithook(_audit_hook)


def _writes_under_data(writes) -> list[str]:
    data_root = str((REPO / "data").resolve())
    out = []
    for w in writes:
        w = w.decode() if isinstance(w, bytes) else str(w)
        try:
            resolved = str(Path(w).resolve())
        except Exception:
            continue
        if resolved == data_root or resolved.startswith(data_root + os.sep):
            out.append(resolved)
    return out


def test_sim_run_leaves_real_data_and_endpoints_untouched(tmp_path):
    from fastapi.testclient import TestClient

    from modules.sim import api as sim_api
    from modules.sim.analysis import run_world
    from modules.sim.store import InMemoryBackend
    from modules.sim.synthetic import build_synthetic_snapshot
    from modules.sim.types import Strategy
    from services import mobile_api_service as svc

    real = TestClient(svc.app)
    endpoints = ["/health", "/v1/app-config"]
    before_json = {p: real.get(p).json() for p in endpoints}
    _audit_state.update(active=True, writes=[])
    db = REPO / "data" / "players.db"
    db_hash = hashlib.sha256(db.read_bytes()).hexdigest() if db.exists() else ""

    snap = build_synthetic_snapshot(3)
    for seed in range(3):
        run_world(snap, Strategy(posture="win_now", trade_aggressiveness=1.0), seed)
    # and a full API round trip against an in-memory backend
    from fastapi import FastAPI

    app = FastAPI()
    backend = InMemoryBackend()

    class Inputs:
        def league_snapshot(self, *a, **k):
            return snap

    sim_api.mount(
        app,
        sim_api.SimApiDeps(
            require_user=lambda: {"id": "u1"}, is_pro=lambda u: True, sleeper_username=lambda u: "",
            backend_for=lambda u: backend, inputs=Inputs(),
        ),
        environ={"SIM_ENABLED": "1"},
    )
    client = TestClient(app)
    wid = client.post("/v1/sim/worlds", json={"league_id": "L"}).json()["world"]["id"]
    assert client.post(f"/v1/sim/worlds/{wid}/run").json()["result"]["grade"]

    assert {p: real.get(p).json() for p in endpoints} == before_json
    _audit_state["active"] = False
    assert _writes_under_data(_audit_state["writes"]) == []
    if db.exists():
        assert hashlib.sha256(db.read_bytes()).hexdigest() == db_hash


def test_a_full_game_leaves_real_data_untouched_and_writes_only_sim_tables():
    """Play a whole GM game through the API: nothing under data/ is written,
    real endpoints are unchanged, and the only tables touched are sim_games,
    sim_events and sim_week_checkpoints."""

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from modules.sim import api as sim_api
    from modules.sim import game_api
    from modules.sim.inputs import PlayerPool
    from modules.sim.store import InMemoryBackend
    from modules.sim.synthetic import build_synthetic_pool
    from services import mobile_api_service as svc

    rows, byes = build_synthetic_pool(7)

    class Inputs:
        def player_pool(self, scoring):
            return PlayerPool(rows, byes)

    real = TestClient(svc.app)
    endpoints = ["/health", "/v1/app-config"]
    before_json = {p: real.get(p).json() for p in endpoints}
    db = REPO / "data" / "players.db"
    db_hash = hashlib.sha256(db.read_bytes()).hexdigest() if db.exists() else ""
    game_api.clear_pool_cache()
    _audit_state.update(active=True, writes=[])

    app = FastAPI()
    backend = InMemoryBackend()
    sim_api.mount(
        app,
        sim_api.SimApiDeps(
            require_user=lambda: {"id": "u1"}, is_pro=lambda u: True, sleeper_username=lambda u: "",
            backend_for=lambda u: backend, inputs=Inputs(),
        ),
        environ={"SIM_ENABLED": "1"},
    )
    client = TestClient(app)
    gid = client.post("/v1/sim/games", json={"user_slot": 3}).json()["game"]["id"]
    assert client.post(f"/v1/sim/games/{gid}/draft/auto").json()["completed"] is True
    for _ in range(20):
        if client.post(f"/v1/sim/games/{gid}/advance").json()["game"]["status"] == "complete":
            break
    assert client.get(f"/v1/sim/games/{gid}/result").json()["result"]["grade"]["letter"]
    assert client.get("/v1/sim/preview/players").json()["total"] > 0

    _audit_state["active"] = False
    assert set(backend.tables) <= {"sim_games", "sim_events", "sim_week_checkpoints"}
    assert {p: real.get(p).json() for p in endpoints} == before_json
    assert _writes_under_data(_audit_state["writes"]) == []
    if db.exists():
        assert hashlib.sha256(db.read_bytes()).hexdigest() == db_hash
    game_api.clear_pool_cache()


def test_player_pool_adapter_reads_players_db_read_only():
    db = REPO / "data" / "players.db"
    if not db.exists():
        pytest.skip("no players.db in this checkout")
    from modules.sim.inputs import RealSimInputs

    class Projections:
        def baseline_weekly_points(self, rows, *, scoring_settings=None):
            return {}

    before = hashlib.sha256(db.read_bytes()).hexdigest()
    before_files = sorted(p.name for p in db.parent.glob("players.db*"))
    pool = RealSimInputs(str(db), projections_module=Projections(), sleeper_module=object(),
                         playoff_module=object()).player_pool({"rec": 1.0})
    positions = {r["pos"] for r in pool.rows}
    # Team defenses are estimated from the cached schedule (data/nfl_games.csv), present in CI, not everywhere.
    assert len(pool.rows) > 300 and positions - {"DEF"} == {"QB", "RB", "WR", "TE", "K"}
    defenses = [r for r in pool.rows if r["pos"] == "DEF"]
    assert not defenses or (len(defenses) == 32 and all(r["pid"].startswith("DEF-") for r in defenses))
    assert all(r["mean"] > 0 and r["sd"] > 0 for r in pool.rows)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in db.parent.glob("players.db*")) == before_files


def test_real_players_db_is_only_ever_read_through_a_readonly_connection():
    """Point the adapter at the real data/players.db (with faked Sleeper): the
    file must be byte-identical afterwards and no journal/wal may appear."""

    db = REPO / "data" / "players.db"
    if not db.exists():
        pytest.skip("no players.db in this checkout")
    from modules.sim.inputs import RealSimInputs

    con = __import__("sqlite3").connect(f"file:{db}?mode=ro", uri=True)
    try:
        ids = [r[0] for r in con.execute(
            "select player_id from players where position in ('QB','RB','WR','TE') and active=1 "
            "order by value desc limit 48"
        )]
    finally:
        con.close()
    if len(ids) < 48:
        pytest.skip("players.db too small")

    class Sleeper:
        def get_league(self, _):
            return {"name": "L", "season": "2026", "roster_positions": ["QB", "RB", "WR", "TE", "FLEX"],
                    "settings": {"leg": 0, "playoff_week_start": 15, "playoff_teams": 4}}

        def get_rosters(self, _):
            return [{"roster_id": i + 1, "players": ids[i * 12:(i + 1) * 12], "settings": {}} for i in range(4)]

        def get_league_roster_profiles(self, _):
            return {str(i + 1): {"team_name": f"T{i}", "owner_name": f"O{i}", "username": f"u{i}"} for i in range(4)}

        def get_matchups_for_weeks(self, *_):
            return {}

    class Projections:
        def baseline_weekly_points(self, rows, *, scoring_settings=None):
            return {}

    class Playoff:
        def playoff_bracket_format(self, *a, **k):
            return {"available": True, "reason": "", "reseed": False}

    before = hashlib.sha256(db.read_bytes()).hexdigest()
    before_files = sorted(p.name for p in db.parent.glob("players.db*"))
    from modules.sim.analysis import run_world
    from modules.sim.types import Strategy

    snap = RealSimInputs(str(db), sleeper_module=Sleeper(), projections_module=Projections(),
                         playoff_module=Playoff()).league_snapshot("L", mode="full", roster_id="1")
    run_world(snap, Strategy(), 1)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in db.parent.glob("players.db*")) == before_files


# ---------------------------------------------------------------- 5. off by default


def _sim_probe_status(app) -> int:
    from fastapi.testclient import TestClient

    return TestClient(app).get("/v1/sim/status").status_code


def test_real_app_registers_no_sim_routes_by_default():
    assert os.environ.get("SIM_ENABLED", "") == "", "run the suite without SIM_ENABLED set"
    from services import mobile_api_service as svc

    assert _sim_probe_status(svc.app) == 404


def test_service_mounts_sim_routes_only_when_flag_set():
    """Fresh interpreter: flag on serves /v1/sim/* (401 without auth), flag off 404s."""

    code = (
        f"import sys; sys.path.insert(0, {str(REPO)!r})\n"
        "from fastapi.testclient import TestClient\n"
        "from services import mobile_api_service as svc\n"
        "c = TestClient(svc.app)\n"
        "print(c.get('/v1/sim/status').status_code, c.get('/v1/sim/worlds').status_code)\n"
    )

    def probe(flag: str | None) -> str:
        env = {k: v for k, v in os.environ.items() if k != "SIM_ENABLED"}
        if flag is not None:
            env["SIM_ENABLED"] = flag
        proc = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, env=env, timeout=180)
        assert proc.returncode == 0, proc.stderr[-2000:]
        return proc.stdout.strip().splitlines()[-1]

    assert probe(None) == "404 404"
    assert probe("0") == "404 404"
    assert probe("1") == "401 401"


def test_import_scanner_sees_every_import_style(tmp_path):
    sample = tmp_path / "x.py"
    sample.write_text(
        "import modules.sim.engine\n"
        "from modules.sim import api\n"
        "from modules import rankings\n"
        "def f():\n    from modules import sleeper\n    import streamlit\n"
        "from . import sibling\n"
    )
    found = _imports(sample)
    assert ("modules.sim.engine", (), 0) in found
    assert ("modules.sim", ("api",), 0) in found
    assert ("modules", ("rankings",), 0) in found
    assert ("modules", ("sleeper",), 0) in found  # function-level imports are seen
    assert ("streamlit", (), 0) in found
    assert ("", ("sibling",), 1) in found
