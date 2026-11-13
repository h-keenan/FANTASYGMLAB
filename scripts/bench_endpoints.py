"""Repeatable backend endpoint benchmark (in-process, fully local).

Measures the top user-facing endpoints of services/mobile_api_service.py with
no real network: a stub HTTP server stands in for Sleeper + Supabase (reused
from scripts/load_test_local.py, 30 ms nominal upstream latency), a throwaway
redis-server backs the shared caches, and the app runs against a COPY of
``data/`` in a temp dir (the real data/players.db is never opened for write).

  python scripts/bench_endpoints.py --out bench.json [--reps 8 --conc 8]
  python scripts/bench_endpoints.py --profile      # adds cProfile top-20

Per endpoint it records:
  cold   first request for a never-seen league (builds frames, hits Sleeper)
  warm   p50 / p95 wall over --reps repeat requests (+ CPU ms per request)
  conc   p50 / p95 wall with --conc simultaneous users, each on its own
         league (cold first hit), plus CPU ms per request
  bytes  median response size
  hash   sha256 of the canonical JSON body (volatile keys stripped), so two
         runs (before/after a change) can be diffed for identical output
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import hashlib
import json
import os
import pstats
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import logging  # noqa: E402

logging.disable(logging.INFO)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import load_test_local as lt  # noqa: E402

ENDPOINT_FILTER: set[str] = set()
VOLATILE = {"playoff_probability", "generated_at", "as_of", "timestamp", "ts", "elapsed_ms", "server_time", "cached_at", "age_seconds", "request_id", "timing", "timings", "_timing"}


UPSTREAM_CALLS: dict[str, int] = {"sleeper": 0, "supabase_auth": 0, "supabase_rest": 0}


def _count_upstream() -> None:
    """Count every upstream request the stub serves, by kind (Sleeper vs Supabase)."""

    original = lt.Stub.do_GET

    def counted(self):  # noqa: ANN001
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        kind = "supabase_auth" if parts[:1] == ["auth"] else "supabase_rest" if parts[:1] == ["rest"] else "sleeper"
        if not self.path.startswith("/__"):
            UPSTREAM_CALLS[kind] += 1
        return original(self)

    lt.Stub.do_GET = counted


def endpoints(n: int) -> list[tuple[str, str, str, dict | None]]:
    """(name, method, path, json_body) for league L{n}; the user owns roster 1."""
    stub = object.__new__(lt.Stub)
    mine = stub._roster(n, 1)["players"]
    theirs = stub._roster(n, 2)["players"]
    L = f"/v1/leagues/L{n}"
    all_eps = [
        ("dashboard", "GET", f"{L}/dashboard", None),
        ("dashboard_deferred", "GET", f"{L}/dashboard?defer_trade_ideas=true", None),
        ("rankings", "GET", f"{L}/rankings?limit=100", None),
        ("team_rankings", "GET", f"{L}/team-rankings", None),
        ("trade_analyzer", "POST", f"{L}/trade-analyzer", {"send_player_ids": mine[3:5], "receive_player_ids": theirs[:1]}),
        ("trade_hub", "GET", f"{L}/trade-hub", None),
        ("trade_finder", "GET", f"{L}/trade-finder", None),
        ("my_roster", "GET", f"{L}/my-roster", None),
        ("my_team", "GET", f"{L}/my-team", None),
        ("player_rank", "GET", f"{L}/players/{mine[0]}/rank", None),
        ("player_quick_view", "GET", f"/v1/players/{mine[0]}/quick-view", None),
        ("player_search", "GET", f"{L}/players/search?q=jo&limit=25", None),
        ("gm_plan", "GET", f"{L}/gm-plan", None),
        ("matchup", "GET", f"{L}/matchup", None),
        ("waivers", "GET", f"{L}/waivers", None),
        ("leagues_glance", "GET", "/v1/leagues-glance", None),
    ]
    return [e for e in all_eps if not ENDPOINT_FILTER or e[0] in ENDPOINT_FILTER]


_AGE_RE = re.compile(r"\b\d+\s?(?:s|m|min|h|d|sec|mins|hours|days)\s+ago\b")


def _strip(o):
    if isinstance(o, str):
        return _AGE_RE.sub("N ago", o)
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k not in VOLATILE}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


BODIES_DIR: Path | None = None
PROF_DIR: Path | None = None


def body_hash(content: bytes) -> str:
    try:
        return hashlib.sha256(json.dumps(_strip(json.loads(content)), sort_keys=True, default=str).encode()).hexdigest()[:16]
    except Exception:
        return hashlib.sha256(content).hexdigest()[:16]


def pct(vals, p):
    s = sorted(vals)
    return round(s[min(len(s) - 1, int(len(s) * p))], 1) if s else 0.0


async def call(client, name, method, path, body, n):
    hdr = {"Authorization": f"Bearer user-{n}.x.y"}
    t0, c0 = time.perf_counter(), time.process_time()
    r = await (client.post(path, json=body, headers=hdr, timeout=300) if method == "POST" else client.get(path, headers=hdr, timeout=300))
    res = {"ms": (time.perf_counter() - t0) * 1000, "cpu_ms": (time.process_time() - c0) * 1000, "status": r.status_code, "bytes": len(r.content), "hash": body_hash(r.content)}
    if BODIES_DIR is not None:
        try:
            canon = json.dumps(_strip(json.loads(r.content)), sort_keys=True, indent=1, default=str)
        except Exception:
            canon = r.text
        res["canon"] = canon
    return res


async def run_single(client, reps, first_league=1):
    out = {}
    for i, (name, method, path, body) in enumerate(endpoints(first_league)):
        league_n = 4 * (100 + i)  # fresh league per endpoint => truly cold; n%4==0 => stub Pro user (no free-tier gates)
        _, m, p, b = endpoints(league_n)[i]
        calls_before = dict(UPSTREAM_CALLS)
        cold = await call(client, name, m, p, b, league_n)
        cold_calls = {k: UPSTREAM_CALLS[k] - calls_before[k] for k in UPSTREAM_CALLS}
        warm = [await call(client, name, m, p, b, league_n) for _ in range(reps)]
        if BODIES_DIR is not None:
            (BODIES_DIR / f"{name}.cold.json").write_text(cold["canon"])
            (BODIES_DIR / f"{name}.warm.json").write_text(warm[-1]["canon"])
        out[name] = {
            "status": cold["status"], "cold_ms": round(cold["ms"], 1), "cold_cpu_ms": round(cold["cpu_ms"], 1),
            "warm_p50_ms": pct([w["ms"] for w in warm], 0.5), "warm_p95_ms": pct([w["ms"] for w in warm], 0.95),
            "warm_cpu_ms": round(statistics.median(w["cpu_ms"] for w in warm), 1),
            "bytes": cold["bytes"], "hash": cold["hash"], "warm_hash": warm[-1]["hash"],
            "cold_upstream_calls": cold_calls,
        }
        print(f"  {name:20s} {cold['status']} cold {cold['ms']:8.0f}ms  warm p50 {out[name]['warm_p50_ms']:7.1f}ms cpu {out[name]['warm_cpu_ms']:7.1f}ms {cold['bytes']:>8}B", flush=True)
    return out


async def run_conc(client, conc):
    out = {}
    names = [e[0] for e in endpoints(1)]
    t_all, c_all = time.perf_counter(), time.process_time()

    async def user(u):
        res = {}
        league_n = 4 * (300 + u)
        for i, name in enumerate(names):
            _, m, p, b = endpoints(league_n)[i]
            res[name] = await call(client, name, m, p, b, league_n)
        return res

    users = await asyncio.gather(*(user(u) for u in range(conc)))
    wall, cpu = time.perf_counter() - t_all, time.process_time() - c_all
    for name in names:
        rows = [u[name] for u in users]
        out[name] = {"p50_ms": pct([r["ms"] for r in rows], 0.5), "p95_ms": pct([r["ms"] for r in rows], 0.95),
                     "cpu_ms": round(statistics.median(r["cpu_ms"] for r in rows), 1),
                     "non200": sum(1 for r in rows if r["status"] != 200)}
    out["__total__"] = {"users": conc, "wall_s": round(wall, 1), "cpu_s": round(cpu, 1), "cpu_s_per_user": round(cpu / conc, 2)}
    return out


PORTFOLIO_PROFILE = False
REVISIT_AGE_SECONDS = 180
PORTFOLIO_CLIENT_CONCURRENCY = 3  # web-next/src/lib/portfolioLoader.ts PORTFOLIO_LEAGUE_CONCURRENCY


async def _portfolio_get(client, path, n):
    t0, c0 = time.perf_counter(), time.process_time()
    r = await client.get(path, headers={"Authorization": f"Bearer user-{n}.x.y"}, timeout=300)
    return {"ms": (time.perf_counter() - t0) * 1000, "cpu_ms": (time.process_time() - c0) * 1000, "status": r.status_code, "bytes": len(r.content), "body": r.content}


async def portfolio_visit(client, n, defer=True):
    """One Portfolio page visit, driven exactly like the web/mobile clients: the
    cheap index, then every league row with PORTFOLIO_CLIENT_CONCURRENCY
    requests in flight, in saved order. With `defer` the per-league request is
    headline-first (`signals=defer`); a response flagged `signals_pending` is
    followed by a second, full request, queued behind every league's headline
    (a server that predates the parameter just answers in full). Returns timings
    (ms from navigation start), bytes, a canonical hash of the FINAL rows, and
    process CPU for the whole visit."""

    t0, c0 = time.perf_counter(), time.process_time()
    calls0 = dict(UPSTREAM_CALLS)
    idx = await _portfolio_get(client, "/v1/portfolio/leagues?lens=Dynasty", n)
    t_index = (time.perf_counter() - t0) * 1000
    index = json.loads(idx["body"])
    ids = [x["league_id"] for x in index.get("saved_leagues", [])]
    queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
    for pos, lid in enumerate(ids):
        queue.put_nowait((0, pos, lid))
    final: dict[str, dict] = {}
    headline_at: dict[str, float] = {}
    final_at: dict[str, float] = {}
    req_ms: list[float] = []
    nbytes = {"headline": 0, "full": 0}
    remaining = len(ids)

    async def worker():
        nonlocal remaining
        while remaining > 0:
            try:
                phase, pos, lid = await asyncio.wait_for(queue.get(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            suffix = "&signals=defer" if (defer and phase == 0) else ""
            res = await _portfolio_get(client, f"/v1/portfolio/leagues/{lid}?lens=Dynasty{suffix}", n)
            req_ms.append(res["ms"])
            now = (time.perf_counter() - t0) * 1000
            body = json.loads(res["body"])
            if phase == 0:
                headline_at[lid] = now
            if body.get("signals_pending") and phase == 0:
                nbytes["headline"] += res["bytes"]
                queue.put_nowait((1, pos, lid))
                continue
            nbytes["full"] += res["bytes"]
            final[lid] = res
            final_at[lid] = now
            remaining -= 1

    await asyncio.gather(*(worker() for _ in range(PORTFOLIO_CLIENT_CONCURRENCY)))
    total_ms = (time.perf_counter() - t0) * 1000
    composed = [json.loads(final[lid]["body"]) for lid in ids]
    canon = json.dumps(_strip(composed), sort_keys=True, default=str)
    hl = sorted(headline_at.values())
    fin = sorted(final_at.values())
    return {
        "leagues": len(ids), "index_ms": round(t_index, 1), "index_bytes": idx["bytes"],
        "first_card_ms": round(hl[0], 1) if hl else None,
        "all_headlines_ms": round(hl[-1], 1) if hl else None,
        "first_full_card_ms": round(fin[0], 1) if fin else None,
        "all_cards_ms": round(total_ms, 1),
        "req_ms_p50": round(statistics.median(req_ms), 1) if req_ms else None,
        "req_ms_max": round(max(req_ms), 1) if req_ms else None,
        "requests": len(req_ms),
        "league_bytes_total": nbytes["headline"] + nbytes["full"],
        "league_bytes_final_median": int(statistics.median(r["bytes"] for r in final.values())) if final else 0,
        "cpu_ms": round((time.process_time() - c0) * 1000, 1),
        "non200": sum(1 for r in final.values() if r["status"] != 200) + (idx["status"] != 200),
        "upstream": {k: UPSTREAM_CALLS[k] - calls0[k] for k in UPSTREAM_CALLS},
        "hash": hashlib.sha256(canon.encode()).hexdigest()[:16],
        "_canon": canon,
    }


def age_caches(seconds: float) -> int:
    """Simulate `seconds` passing for everything Portfolio caches in Redis: the 120 s
    time-bucketed layers (valued frame, rankings, trade ideas, Sleeper reads...) are
    dropped, finished Portfolio rows get their timestamp moved back. Saved-leagues,
    profile and rollover entries are kept (they are re-read every visit either way)."""

    import redis as _redis

    client = _redis.Redis.from_url(os.environ["REDIS_URL"])
    dropped = 0
    for key in client.scan_iter("*"):
        name = key.decode()
        if "portfolio_row" in name and not name.startswith("lock:"):
            envelope = json.loads(client.get(key))
            envelope["ts"] -= seconds
            client.set(key, json.dumps(envelope), ex=3600)
        elif not name.startswith("lock:") and not any(t in name for t in ("saved_leagues", "profile_fields", "league_rollover", "team_stance", "gm_target")):
            client.delete(key)
            dropped += 1
    return dropped


async def run_portfolio(client, counts, reps, defer=True):
    """Portfolio for a user with N leagues: cold visit (fresh user, process warm),
    warm revisits, and the legacy single-shot GET /v1/portfolio."""

    out = {}
    # Process warm-up (imports, redis connect, shared player frames) on a throwaway user.
    os.environ["LT_LEAGUES_PER_USER"] = "1"
    await portfolio_visit(client, 4 * 650, defer)
    if PORTFOLIO_PROFILE:
        os.environ["LT_LEAGUES_PER_USER"] = "1"
        pr = cProfile.Profile()
        pr.enable()
        await portfolio_visit(client, 4 * 660, defer)
        pr.disable()
        if PROF_DIR is not None:
            pr.dump_stats(str(PROF_DIR / "portfolio_cold_1_league.prof"))
        st = pstats.Stats(pr)
        out["profile_cold_1_league"] = {"top_self": _rows(st, 25), "repo_cumulative": _cum_rows(st, 40)}
        for r in out["profile_cold_1_league"]["repo_cumulative"]:
            print(f"{r['cumtime_ms']:9.1f}ms cum {r['calls']:>6} {r['fn']}")
    for count in counts:
        os.environ["LT_LEAGUES_PER_USER"] = str(count)
        base = 4 * (700 + 40 * count)
        cold = await portfolio_visit(client, base, defer)
        warm = [await portfolio_visit(client, base, defer) for _ in range(reps)]
        age_caches(REVISIT_AGE_SECONDS)
        await asyncio.sleep(0.3)
        revisit = await portfolio_visit(client, base, defer)
        revisit.pop("_canon")
        await asyncio.sleep(3)  # let a stale-while-revalidate refresh finish before the next phase
        calls0 = dict(UPSTREAM_CALLS)
        legacy = await _portfolio_get(client, "/v1/portfolio?lens=Dynasty", base + 4 * 20)
        legacy_calls = {k: UPSTREAM_CALLS[k] - calls0[k] for k in UPSTREAM_CALLS}
        legacy_warm = await _portfolio_get(client, "/v1/portfolio?lens=Dynasty", base + 4 * 20)
        canon = cold.pop("_canon")
        for w in warm:
            w.pop("_canon")
        if BODIES_DIR is not None:
            (BODIES_DIR / f"portfolio_{count}.cold.json").write_text(json.dumps(json.loads(canon), indent=1, sort_keys=True))
        med = lambda key: round(statistics.median(w[key] for w in warm), 1)  # noqa: E731
        out[str(count)] = {
            "cold": cold,
            "warm": {k: med(k) for k in ("index_ms", "first_card_ms", "all_headlines_ms", "all_cards_ms", "cpu_ms")},
            "warm_hash": warm[-1]["hash"],
            "revisit_after_expiry": revisit,
            "legacy_cold_ms": round(legacy["ms"], 1), "legacy_cold_cpu_ms": round(legacy["cpu_ms"], 1),
            "legacy_warm_ms": round(legacy_warm["ms"], 1), "legacy_bytes": legacy["bytes"],
            "legacy_upstream": legacy_calls, "legacy_hash": body_hash(legacy["body"]),
        }
        c = cold
        print(f"  {count:>2} leagues  cold: index {c['index_ms']:6.0f}ms first card {c['first_card_ms']:7.0f}ms headlines {c['all_headlines_ms']:7.0f}ms all {c['all_cards_ms']:7.0f}ms cpu {c['cpu_ms']:7.0f}ms"
              f" | warm all {out[str(count)]['warm']['all_cards_ms']:7.0f}ms | legacy cold {legacy['ms']:7.0f}ms warm {legacy_warm['ms']:6.0f}ms"
              f" | revisit@3min first {revisit['first_card_ms']:.0f}ms all {revisit['all_cards_ms']:.0f}ms cpu {revisit['cpu_ms']:.0f}ms"
              f" | upstream {c['upstream']} {c['league_bytes_total']}B", flush=True)
    return out


def _rows(st, top):
    rows = sorted(st.stats.items(), key=lambda kv: kv[1][2], reverse=True)[:top]
    return [{"fn": f"{k[2]} ({Path(k[0]).name}:{k[1]})", "tottime_ms": round(v[2] * 1000, 1), "cumtime_ms": round(v[3] * 1000, 1), "calls": v[1]} for k, v in rows]


def _cum_rows(st, top):
    """Highest cumulative time among repo-owned functions: where the cost is *called from*."""
    own = [(k, v) for k, v in st.stats.items() if str(ROOT) in k[0] and "bench_endpoints" not in k[0]]
    own.sort(key=lambda kv: kv[1][3], reverse=True)
    return [{"fn": f"{k[2]} ({Path(k[0]).relative_to(ROOT)}:{k[1]})", "cumtime_ms": round(v[3] * 1000, 1), "calls": v[1]} for k, v in own[:top]]


async def run_profile(client, top):
    """cProfile per endpoint: one cold (fresh league) and one warm request.

    cProfile is interpreter-global on 3.12+, so the sync handlers running in
    the threadpool are captured too.
    """
    names = [e[0] for e in endpoints(1)]
    out = {"cold": {}, "warm": {}}
    for phase in ("cold", "warm"):
        agg = None
        per = {}
        for i, name in enumerate(names):
            league_n = 4 * (500 + i + (100 if phase == "cold" else 0))
            _, m, p, b = endpoints(league_n)[i]
            if phase == "warm":
                await call(client, name, m, p, b, league_n)
            pr = cProfile.Profile()
            pr.enable()
            await call(client, name, m, p, b, league_n)
            pr.disable()
            st = pstats.Stats(pr)
            if PROF_DIR is not None:
                pr.dump_stats(str(PROF_DIR / f"{name}.{phase}.prof"))
            agg = st if agg is None else (agg.add(st) or agg)
            per[name] = _cum_rows(st, 5)
        out[phase] = {"top20_self": _rows(agg, top), "top20_repo_cumulative": _cum_rows(agg, top), "per_endpoint_repo_cum_top5": per}
    return out


def _free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=8)
    ap.add_argument("--conc", type=int, default=8)
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--only", default="", help="skip phases: single,conc")
    ap.add_argument("--portfolio", default="", help="comma-separated league counts (e.g. 1,5,12): run ONLY the Portfolio flow for users with that many leagues")
    ap.add_argument("--portfolio-flow", default="defer", choices=["defer", "plain"], help="client flow for --portfolio: headline-first (default) or one full request per league")
    ap.add_argument("--endpoints", default="", help="comma-separated endpoint names to run (default all)")
    ap.add_argument("--bodies-dir", default="", help="write canonical (volatile-stripped) response bodies here for before/after diffing")
    ap.add_argument("--prof-dir", default="", help="with --profile: keep raw per-endpoint .prof files here (pstats/snakeviz)")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    global BODIES_DIR, PROF_DIR, PORTFOLIO_PROFILE
    PORTFOLIO_PROFILE = a.profile
    if a.prof_dir:
        PROF_DIR = Path(a.prof_dir)
        PROF_DIR.mkdir(parents=True, exist_ok=True)
    if a.bodies_dir:
        BODIES_DIR = Path(a.bodies_dir)
        BODIES_DIR.mkdir(parents=True, exist_ok=True)
    ENDPOINT_FILTER.update(x for x in a.endpoints.split(",") if x)
    if a.portfolio:
        # Portfolio flow: Sleeper 30-60 ms, Supabase ~30 ms per call, unless the caller overrode them.
        os.environ.setdefault("LT_LATENCY_MS", "30,60")
        os.environ.setdefault("LT_SUPABASE_LATENCY_MS", "30")

    guarded = [ROOT / "data" / n for n in ("players.db", "sleeper_players.json")]
    before_hash = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in guarded if f.exists()}
    REDIS_PORT = _free_port()  # never share a cache with another run
    work = Path(tempfile.mkdtemp(prefix="bench_"))
    shutil.copytree(ROOT / "data", work / "data")
    os.environ["LT_PLAYERS_JSON"] = str(work / "data/sleeper_players.json")
    _count_upstream()
    threading.Thread(target=lt.run_stub, daemon=True).start()
    redis_proc = subprocess.Popen(["redis-server", "--port", str(REDIS_PORT), "--save", "", "--appendonly", "no"], stdout=subprocess.DEVNULL, cwd=work)
    time.sleep(1)
    # require_user() would otherwise spawn a real players.db refresh subprocess
    # (cwd = repo root, live Sleeper network) when the copied dump looks stale.
    os.environ["DYNASTYGM_TEST_MODE"] = "1"
    os.environ.update(REDIS_URL=f"redis://127.0.0.1:{REDIS_PORT}/0", SUPABASE_URL=f"http://127.0.0.1:{lt.STUB_PORT}", SUPABASE_ANON_KEY="anon-bench")
    os.chdir(work)  # app resolves data/players.db relative to cwd => the throwaway copy
    try:
        app = lt.make_app()
        from modules import sleeper

        # The stub serves no player dump; keep the copied (real) dump "fresh" so
        # requests never take the blocking-refresh path, as in production.
        sleeper.PLAYERS_CACHE_TTL_SECONDS = 10**9
        import httpx

        async def go():
            result = {}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bench") as c:
                if a.portfolio:
                    print("portfolio:", flush=True)
                    result["portfolio"] = await run_portfolio(c, [int(x) for x in a.portfolio.split(",")], a.reps, a.portfolio_flow == "defer")
                    return result
                if "single" not in a.only:
                    print("single-user:", flush=True)
                    result["single"] = await run_single(c, a.reps)
                if "conc" not in a.only:
                    print(f"concurrent ({a.conc} users):", flush=True)
                    result["concurrent"] = await run_conc(c, a.conc)
                    print(json.dumps(result["concurrent"]["__total__"]))
                if a.profile:
                    print("profile:", flush=True)
                    result["profile"] = await run_profile(c, 20)
            return result

        result = asyncio.run(go())
        result["sleeper_calls"] = dict(lt.Stub.sleeper_hits)
        text = json.dumps(result, indent=2)
        if a.out:
            Path(a.out).write_text(text)
        if a.profile:
            for phase in ("cold", "warm"):
                print(f"--- top-20 self time, {phase}")
                for r in result["profile"][phase]["top20_self"]:
                    print(f"{r['tottime_ms']:9.1f}ms tot {r['cumtime_ms']:9.1f}ms cum {r['calls']:>8} {r['fn']}")
    except BaseException:
        import traceback

        traceback.print_exc()
        raise
    finally:
        redis_proc.terminate()
        os.chdir(ROOT)
        for f, digest in before_hash.items():
            if hashlib.sha256(f.read_bytes()).hexdigest() != digest:
                print(f"WARNING: {f} changed during the run (the benchmark must only touch its temp copy)", file=sys.stderr)
        shutil.rmtree(work, ignore_errors=True)
        sys.stdout.flush()
        os._exit(0)


if __name__ == "__main__":
    main()
