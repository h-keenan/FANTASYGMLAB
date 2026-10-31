"""Local-only load-test harness for services/mobile_api_service.py.

NEVER points at production: a stub HTTP server stands in for BOTH Sleeper and
Supabase (counting every Sleeper request), a throwaway redis-server is shared by
all uvicorn workers share it, and the app runs against a COPY of ``data/``.

  python scripts/load_test_local.py --users 50 --workers 4 --out results.json

Needs the project venv (fastapi, uvicorn, httpx) and redis-server on PATH. Standalone runner:
it spawns the stub, redis, uvicorn, drives the flows, then tears everything down.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
STUB_PORT, REDIS_PORT, API_PORT = 18700, 18701, 18702
SEASON, WEEK = 2026, 7
FLOWS = [
    ("dashboard", "/v1/leagues/{L}/dashboard"),
    ("my_team", "/v1/leagues/{L}/my-team"),
    ("trade_hub_ideas", "/v1/leagues/{L}/trade-hub"),
    ("matchup", "/v1/leagues/{L}/matchup"),
    ("waivers", "/v1/leagues/{L}/waivers"),
    ("playoff_odds", "/v1/leagues/{L}/playoff-odds"),
]


# --------------------------------------------------------------- stub server
def _players() -> dict:
    return json.load(open(os.environ.get("LT_PLAYERS_JSON", "data/sleeper_players.json")))


class Stub(BaseHTTPRequestHandler):
    sleeper_hits: Counter = Counter()
    unhandled: Counter = Counter()
    pools: dict = {}
    lock = threading.Lock()

    def log_message(self, *a):  # quiet
        pass

    def _send(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @classmethod
    def pool(cls):
        if not cls.pools:
            by = defaultdict(list)
            for pid, p in _players().items():
                if p.get("active") and p.get("team") and p.get("position") in ("QB", "RB", "WR", "TE"):
                    by[p["position"]].append(pid)
            for k in by:
                by[k].sort(key=lambda x: int(x) if x.isdigit() else 0)
            cls.pools = dict(by)
        return cls.pools

    def _league_n(self, league_id: str) -> int:
        return int(league_id.lstrip("L") or 0)

    def _roster(self, n: int, rid: int) -> dict:
        pool, ids = self.pool(), []
        take = {"QB": 3, "RB": 7, "WR": 9, "TE": 3}
        for pos, cnt in take.items():
            p = pool[pos]
            start = ((n * 12 + rid) * 7) % max(1, len(p) - cnt)
            ids += p[start : start + cnt]
        return {
            "roster_id": rid,
            "owner_id": f"sl{n}_{rid}",
            "players": ids,
            "starters": ids[:9],
            "reserve": [],
            "settings": {"wins": rid % 5 + 2, "losses": 5 - rid % 5, "ties": 0, "fpts": 700 + rid * 11, "fpts_decimal": 0, "fpts_against": 650 + rid * 9},
        }

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if parts[:2] == ["auth", "v1"]:
            tok = (self.headers.get("Authorization") or "").replace("Bearer ", "")
            return self._send({"id": f"uid-{tok.split('.')[0]}", "email": f"{tok}@loadtest.invalid"})
        if parts[:2] == ["rest", "v1"]:
            q = parse_qs(u.query)
            uid = (q.get("user_id") or [""])[0].replace("eq.", "")
            n = int(uid.split("-")[-1] or 0) if uid else 0
            if parts[2] == "profiles":
                return self._send([{"entitlement": "pro" if n % 4 == 0 else "free", "sleeper_username": f"sluser{n}"}])
            if parts[2] == "saved_leagues":
                return self._send([{"user_id": uid, "sleeper_username": f"sluser{n}", "league_id": f"L{n}", "league_name": f"Load League {n}", "roster_id": "1", "team_id": "1", "owner_id": f"sl{n}_1", "is_default": True}])
            return self._send([])
        # ---- Sleeper
        with self.lock:
            self.sleeper_hits["/".join(["*" if p.isdigit() or p.startswith(("L", "sl")) else p for p in parts[:4]])] += 1
            self.sleeper_hits["__total__"] += 1
        time.sleep(0.03)  # nominal upstream latency
        if parts[:1] == ["__stats"]:
            return self._send({"hits": self.sleeper_hits, "unhandled": self.unhandled})
        if parts[:2] == ["v1", "state"]:
            return self._send({"season": str(SEASON), "week": WEEK, "leg": WEEK, "season_type": "regular", "display_week": WEEK})
        if len(parts) >= 3 and parts[1] == "user" and len(parts) == 3:
            name = parts[2]
            n = int(name.replace("sluser", "") or 0)
            return self._send({"user_id": f"sl{n}_1", "username": name})
        if len(parts) >= 5 and parts[1] == "user" and parts[3] == "leagues":
            n = int(parts[2].split("_")[0].replace("sl", ""))
            return self._send([{"league_id": f"L{n}", "name": f"Load League {n}", "season": parts[5], "status": "in_season", "previous_league_id": None}])
        if len(parts) >= 3 and parts[1] == "league":
            lid, n = parts[2], self._league_n(parts[2])
            tail = parts[3:]
            if not tail:
                return self._send({"league_id": lid, "name": f"Load League {n}", "season": str(SEASON), "status": "in_season", "total_rosters": 12,
                                   "roster_positions": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "FLEX", "BN", "BN", "BN", "BN", "BN", "BN"],
                                   "scoring_settings": {"rec": 1.0, "pass_td": 4.0, "rush_td": 6.0, "rec_td": 6.0, "pass_yd": 0.04, "rush_yd": 0.1, "rec_yd": 0.1},
                                   "settings": {"num_teams": 12, "playoff_week_start": 15, "playoff_teams": 6, "leg": WEEK, "trade_deadline": 12, "type": 2},
                                   "previous_league_id": None})
            if tail == ["users"]:
                return self._send([{"user_id": f"sl{n}_{r}", "display_name": f"Mgr{r}", "avatar": None, "metadata": {"team_name": f"Team {r}"}} for r in range(1, 13)])
            if tail == ["rosters"]:
                return self._send([self._roster(n, r) for r in range(1, 13)])
            if tail[0] == "matchups":
                wk = int(tail[1])
                return self._send([{"roster_id": r, "matchup_id": (r + 1) // 2, "points": 90 + r if wk < WEEK else 0.0,
                                    "starters": self._roster(n, r)["starters"], "players": self._roster(n, r)["players"]} for r in range(1, 13)])
            if tail[0] in ("transactions",):
                return self._send([])
            if tail[0] in ("drafts", "traded_picks", "winners_bracket", "losers_bracket"):
                return self._send([])
        if parts[:3] == ["v1", "players", "nfl"]:
            return self._send([] if "trending" in parts else {}, 200 if "trending" in parts else 404)
        if parts[:3] == ["v1", "stats", "nfl"]:
            return self._send({})
        with self.lock:
            self.unhandled[self.path] += 1
        self._send({}, 404)

    do_POST = do_PATCH = do_DELETE = lambda self: self._send([])  # noqa: E731


def run_stub():
    ThreadingHTTPServer(("127.0.0.1", STUB_PORT), Stub).serve_forever()


# --------------------------------------------------------------- app wrapper
def make_app():
    """uvicorn target ``scripts.load_test_local:app``: patches Sleeper base URLs only."""
    from modules import redis_cache, sleeper, sleeper_leagues

    base = f"http://127.0.0.1:{STUB_PORT}/v1"
    sleeper.SLEEPER_BASE = sleeper_leagues.SLEEPER_BASE = base
    sleeper.SLEEPER_REQUEST_RETRY_BACKOFF_SECONDS = 0.01
    from services import mobile_api_service

    prof_dir = os.environ.get("LT_PROFILE_DIR")
    if prof_dir:
        _install_profiler(mobile_api_service.app, prof_dir)
    return mobile_api_service.app


def _install_profiler(fastapi_app, prof_dir: str) -> None:
    """Dump a cProfile .prof per profiled request (LT_PROFILE_PATHS, default dashboard).

    Endpoints are sync ``def`` handlers run on a threadpool, so the route's
    endpoint callable is wrapped rather than the ASGI call.
    """
    import cProfile
    import functools
    import itertools

    wanted = tuple(os.environ.get("LT_PROFILE_PATHS", "/dashboard").split(","))
    counter = itertools.count()
    Path(prof_dir).mkdir(parents=True, exist_ok=True)
    for route in fastapi_app.routes:
        path = getattr(route, "path", "")
        if not path.endswith(wanted):
            continue
        original = route.dependant.call

        @functools.wraps(original)
        def wrapped(*a, __orig=original, __path=path, **kw):
            if os.environ.get("LT_PROFILER") == "pyinstrument":
                # cProfile is interpreter-global on 3.12+ (sys.monitoring) and mixes threads;
                # pyinstrument samples only the calling thread.
                from pyinstrument import Profiler

                name = __path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
                prof = Profiler(interval=0.002)
                prof.start()
                try:
                    return __orig(*a, **kw)
                finally:
                    prof.stop()
                    (Path(prof_dir) / f"{name}.{os.getpid()}.{next(counter)}.txt").write_text(prof.output_text(unicode=False, color=False, show_all=False))
            pr = cProfile.Profile()
            try:
                return pr.runcall(__orig, *a, **kw)
            finally:
                name = __path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
                pr.dump_stats(str(Path(prof_dir) / f"{name}.{os.getpid()}.{next(counter)}.prof"))

        route.dependant.call = wrapped


if os.environ.get("LT_APP") == "1":
    app = make_app()


# --------------------------------------------------------------------- driver
def pct(vals, p):
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * p))] if s else 0.0


sizes: dict = defaultdict(list)
PROGRESSIVE = False
TIMEOUT = 180.0


async def user_session(client, n, results, errors, delay=0.0):
    await asyncio.sleep(delay)
    hdr = {"Authorization": f"Bearer user-{n}.x.y"}
    t_session = time.perf_counter()
    for name, path in FLOWS:
        if name == "dashboard" and PROGRESSIVE:
            # What web/mobile now do: first paint without trade ideas, then the full call.
            t0 = time.perf_counter()
            try:
                r = await client.get(path.replace("{L}", f"L{n}") + "?defer_trade_ideas=true", headers=hdr, timeout=TIMEOUT)
                results["dashboard_first_paint"].append((time.perf_counter() - t0) * 1000)
                if r.status_code < 400:
                    results["ux_first_paint"].append((time.perf_counter() - t_session) * 1000)
                if r.status_code >= 400:
                    print("ERRBODY", r.status_code, r.text[:300], file=sys.stderr)
                    errors[f"dashboard_first_paint {r.status_code}"] += 1
            except Exception as exc:
                errors[f"dashboard_first_paint {type(exc).__name__}"] += 1
            t0 = time.perf_counter()
        t0 = time.perf_counter()
        try:
            r = await client.get(path.replace("{L}", f"L{n}"), headers=hdr, timeout=TIMEOUT)
            ms = (time.perf_counter() - t0) * 1000
            results[name].append(ms)
            sizes[name].append(len(r.content))
            if name == "dashboard" and r.status_code < 400:
                # Time from the user opening the app to a fully rendered dashboard.
                results["ux_full"].append((time.perf_counter() - t_session) * 1000)
                if not PROGRESSIVE:
                    results["ux_first_paint"].append(results["ux_full"][-1])
            if r.status_code >= 400:
                errors[f"{name} {r.status_code}"] += 1
        except Exception as exc:
            errors[f"{name} {type(exc).__name__}"] += 1
        await asyncio.sleep(0.2)  # think time


async def drive(users: int, ramp: float = 0.0):
    import httpx

    results, errors = defaultdict(list), Counter()
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{API_PORT}", limits=httpx.Limits(max_connections=users * 2)) as c:
        t0 = time.perf_counter()
        await asyncio.gather(*(user_session(c, n, results, errors, ramp * n / users) for n in range(1, users + 1)))
        wall = time.perf_counter() - t0
    return results, errors, wall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ramp", type=float, default=0.0, help="spread user arrivals over N seconds (0 = thundering herd)")
    ap.add_argument("--out", default="")
    ap.add_argument("--profile-dir", default="", help="write per-request cProfile dumps of the dashboard handler here")
    ap.add_argument("--data-dir", default="", help="source of the throwaway data/ copy (default: <repo>/data); "
                    "use when a worktree's tracked data/ holds stubs instead of the real players dump")
    ap.add_argument("--timeout", type=float, default=180.0, help="per-request client timeout (s)")
    ap.add_argument("--progressive", action="store_true", help="dashboard flow = deferred first paint then full call")
    a = ap.parse_args()
    global PROGRESSIVE
    PROGRESSIVE = a.progressive
    global TIMEOUT
    TIMEOUT = a.timeout
    work = Path(tempfile.mkdtemp(prefix="loadtest_"))
    shutil.copytree(Path(a.data_dir) if a.data_dir else ROOT / "data", work / "data")  # throwaway copy; app cwd is here
    os.environ["LT_PLAYERS_JSON"] = str(work / "data/sleeper_players.json")  # the stub reads it in this process
    threading.Thread(target=run_stub, daemon=True).start()

    redis_proc = subprocess.Popen(["redis-server", "--port", str(REDIS_PORT), "--save", "", "--appendonly", "no"],
                                  stdout=subprocess.DEVNULL, cwd=work)
    time.sleep(1)
    env = dict(os.environ, LT_APP="1", PYTHONPATH=str(ROOT), REDIS_URL=f"redis://127.0.0.1:{REDIS_PORT}/0",
               SUPABASE_URL=f"http://127.0.0.1:{STUB_PORT}", SUPABASE_ANON_KEY="anon-loadtest",
               LT_PLAYERS_JSON=str(work / "data/sleeper_players.json"))
    if a.profile_dir:
        env["LT_PROFILE_DIR"] = a.profile_dir
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "scripts.load_test_local:app", "--port", str(API_PORT),
                             "--workers", str(a.workers), "--log-level", "warning"], cwd=work, env=env,
                            stderr=open(work / "api.log", "w"))
    try:
        import httpx

        for _ in range(120):
            try:
                if httpx.get(f"http://127.0.0.1:{API_PORT}/health", timeout=2).status_code < 500:
                    break
            except Exception:
                time.sleep(1)
        results, errors, wall = asyncio.run(drive(a.users, a.ramp))
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except Exception:
            pass
        import resource

        # CPU burned by the API workers (+ redis), a far less noisy metric than wall time on a busy box.
        cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_s = cpu.ru_utime + cpu.ru_stime
        stats = json.load(urllib_open(f"http://127.0.0.1:{STUB_PORT}/__stats")) if False else None
        out = {"users": a.users, "ramp_s": a.ramp, "workers": a.workers, "wall_s": round(wall, 1), "errors": dict(errors),
               "sleeper_calls": dict(Stub.sleeper_hits), "unhandled_sleeper_paths": dict(Stub.unhandled),
               "endpoints": {k: {"n": len(v), "p50_ms": round(statistics.median(v)), "p95_ms": round(pct(v, 0.95)), "max_ms": round(max(v)), "median_bytes": int(statistics.median(sizes[k])) if sizes[k] else 0} for k, v in results.items()}}
        out["dashboard_completion_rate"] = round(len(results["ux_full"]) / a.users, 3)
        out["cpu_s_total"] = round(cpu_s, 1)
        out["cpu_s_per_user"] = round(cpu_s / a.users, 2)
        out["sleeper_calls_per_session"] = round(Stub.sleeper_hits["__total__"] / a.users, 1)
        print(json.dumps(out, indent=2))
        if a.out:
            Path(a.out).write_text(json.dumps(out, indent=2))
    finally:
        proc.terminate()
        redis_proc.terminate()
        if os.environ.get('LT_KEEP_LOG'):
            shutil.copy(work / 'api.log', os.environ['LT_KEEP_LOG'])
        shutil.rmtree(work, ignore_errors=True)
        sys.stdout.flush()
        os._exit(0)


if __name__ == "__main__":
    main()
