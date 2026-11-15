"""Interleaved A/B of modules.derived_cache on the Desk endpoints that use it (Waivers, Trade Analyzer).

Same throwaway setup as scripts/bench_endpoints.py (stub Sleeper + Supabase, throwaway Redis, a COPY of data/; the real
data/players.db is never opened for write). Every request alternates the memo OFF / ON inside one process, so machine noise
(other agents, thermal) hits both arms equally, and EVERY response pair is compared: the cached body must equal the uncached
body field for field (volatile timestamps stripped). Trade Analyzer is driven with several different packages per league, not
one repeated request, so a hit means "same league, same inputs" and a different package must still compute correctly.

  python scripts/bench_derived_ab.py [--reps 12] [--packages 4] [--out ab.json]

Reports cold (first request for a never-seen league, one league per arm) and warm p50/p95 wall + CPU per arm."""

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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import logging  # noqa: E402

logging.disable(logging.WARNING)

from scripts import bench_endpoints as be  # noqa: E402
from scripts import load_test_local as lt  # noqa: E402


def pct(vals, p):
    s = sorted(vals)
    return round(s[min(len(s) - 1, int(len(s) * p))], 1) if s else 0.0


def packages(n: int, count: int) -> list[dict]:
    stub = object.__new__(lt.Stub)
    mine = stub._roster(n, 1)["players"]
    theirs = stub._roster(n, 2)["players"]
    out = []
    for i in range(count):
        out.append({"send_player_ids": mine[3 + i:5 + i], "receive_player_ids": theirs[i:i + 1 + (i % 2)]})
    return out


async def one(client, derived, enabled: bool, method: str, path: str, body, n: int):
    if derived is not None:
        derived.ENABLED = enabled
    hdr = {"Authorization": f"Bearer user-{n}.x.y"}
    while True:
        t0, c0 = time.perf_counter(), time.process_time()
        r = await (client.post(path, json=body, headers=hdr, timeout=300) if method == "POST" else client.get(path, headers=hdr, timeout=300))
        ms, cpu = (time.perf_counter() - t0) * 1000, (time.process_time() - c0) * 1000
        if r.status_code == 429 or b"Too many requests" in r.content:  # the per-user limiter, not the code under test: back off and retry
            await asyncio.sleep(2.0)
            continue
        break
    canon = json.dumps(be._strip(json.loads(r.content)), sort_keys=True, default=str)
    return {"ms": ms, "cpu": cpu, "status": r.status_code, "canon": canon, "bytes": len(r.content)}


async def dump(client, outdir: Path):
    """Canonical bodies of Waivers and the Trade Analyzer for Pro (n%4==0) and Free leagues and several packages, so two
    code versions (git stash / checkout) can be diffed byte for byte: ``--dump DIR`` then ``diff -r``."""

    outdir.mkdir(parents=True, exist_ok=True)
    for n in (4 * 320, 4 * 321 + 1, 4 * 322 + 2, 4 * 323, 4 * 324 + 1, 4 * 325 + 3):  # Pro and Free leagues
        r = await one(client, None, True, "GET", f"/v1/leagues/L{n}/waivers", None, n)
        (outdir / f"waivers.{n}.json").write_text(r["canon"])
        for i, body in enumerate(packages(n, 3)):
            r = await one(client, None, True, "POST", f"/v1/leagues/L{n}/trade-analyzer", body, n)
            (outdir / f"trade.{n}.{i}.json").write_text(r["canon"])
    return {"dumped": str(outdir)}


async def profile(client, derived, which: str, reps: int, pkgs: int):
    import cProfile
    import pstats

    n = 4 * 330
    plist = packages(n, pkgs)
    reqs = [("GET", f"/v1/leagues/L{n}/waivers", None)] if which == "waivers" else [("POST", f"/v1/leagues/L{n}/trade-analyzer", b) for b in plist]
    for m, p, b in reqs:
        await one(client, derived, True, m, p, b, n)  # warm every shared cache
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(reps):
        for m, p, b in reqs:
            await one(client, derived, True, m, p, b, n)
    pr.disable()
    st = pstats.Stats(pr)
    rows = []
    for (f, l, fn), (cc, nc, tt, ct, callers) in st.stats.items():
        if str(ROOT) in f and "site-packages" not in f and "bench" not in f:
            rows.append((ct, nc, fn, f.split(str(ROOT) + "/")[-1], l))
    rows.sort(reverse=True)
    for ct, nc, fn, f, l in rows[:30]:
        print(f"{ct / (reps * len(reqs)) * 1000:8.1f} ms/req {nc // (reps * len(reqs)):5d} calls {fn} {f}:{l}")
    return {"profiled": which}


async def run(client, derived, reps: int, pkgs: int):
    out: dict = {}
    mismatches = []
    # ---- Waivers: cold one league per arm, then interleaved warm on a third league
    for name, mk in (("waivers", lambda n: ("GET", f"/v1/leagues/L{n}/waivers", None)),):
        cold = {}
        for arm, n in ((False, 4 * 300), (True, 4 * 301)):
            m, p, b = mk(n)
            r = await one(client, derived, arm, m, p, b, n)
            cold[arm] = r["ms"]
        n = 4 * 302
        m, p, b = mk(n)
        await one(client, derived, False, m, p, b, n)  # warm every shared cache (pool, frames) the same for both arms
        arms = {False: [], True: []}
        for _ in range(reps):
            ref = None
            for arm in (False, True):
                r = await one(client, derived, arm, m, p, b, n)
                arms[arm].append(r)
                if arm is False:
                    ref = r["canon"]
                elif r["canon"] != ref:
                    mismatches.append(f"{name}: cached body differs from uncached")
        out[name] = {"cold_ms": {"off": round(cold[False]), "on": round(cold[True])}, **{
            ("off" if not a else "on"): {"p50_ms": pct([x["ms"] for x in v], .5), "p95_ms": pct([x["ms"] for x in v], .95),
                                           "cpu_p50_ms": round(statistics.median(x["cpu"] for x in v), 1)} for a, v in arms.items()}}
    # ---- Trade analyzer: different packages in one league, interleaved
    cold = {}
    for arm, n in ((False, 4 * 310), (True, 4 * 311)):
        r = await one(client, derived, arm, "POST", f"/v1/leagues/L{n}/trade-analyzer", packages(n, 1)[0], n)
        cold[arm] = r["ms"]
    n = 4 * 312
    plist = packages(n, pkgs)
    await one(client, derived, False, "POST", f"/v1/leagues/L{n}/trade-analyzer", plist[0], n)
    arms = {False: [], True: []}
    for _ in range(reps):
        for body in plist:
            ref = None
            for arm in (False, True):
                r = await one(client, derived, arm, "POST", f"/v1/leagues/L{n}/trade-analyzer", body, n)
                arms[arm].append(r)
                if arm is False:
                    ref = r["canon"]
                elif r["canon"] != ref:
                    mismatches.append("trade_analyzer: cached body differs from uncached")
                    if os.environ.get("AB_DEBUG"):
                        a_, b_ = json.loads(ref), json.loads(r["canon"])
                        for k in sorted(set(a_) | set(b_)):
                            if a_.get(k) != b_.get(k):
                                print("DIFF key", k, str(a_.get(k))[:300], "|||", str(b_.get(k))[:300])
    out["trade_analyzer"] = {"cold_ms": {"off": round(cold[False]), "on": round(cold[True])}, **{
        ("off" if not a else "on"): {"p50_ms": pct([x["ms"] for x in v], .5), "p95_ms": pct([x["ms"] for x in v], .95),
                                       "cpu_p50_ms": round(statistics.median(x["cpu"] for x in v), 1)} for a, v in arms.items()}}
    out["mismatches"] = mismatches
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--packages", type=int, default=4)
    ap.add_argument("--out", default="")
    ap.add_argument("--profile", choices=["waivers", "trade"], default="", help="cProfile warm requests of one endpoint (memo ON) and print the top repo functions")
    ap.add_argument("--dump", default="", help="write canonical bodies to DIR instead of benchmarking")
    a = ap.parse_args()
    redis_port = be._free_port()
    work = Path(tempfile.mkdtemp(prefix="bench_ab_"))
    shutil.copytree(ROOT / "data", work / "data")
    os.environ["LT_PLAYERS_JSON"] = str(work / "data/sleeper_players.json")
    threading.Thread(target=lt.run_stub, daemon=True).start()
    redis_proc = subprocess.Popen(["redis-server", "--port", str(redis_port), "--save", "", "--appendonly", "no"], stdout=subprocess.DEVNULL, cwd=work)
    time.sleep(1)
    os.environ["DYNASTYGM_TEST_MODE"] = "1"
    os.environ.update(REDIS_URL=f"redis://127.0.0.1:{redis_port}/0", SUPABASE_URL=f"http://127.0.0.1:{lt.STUB_PORT}", SUPABASE_ANON_KEY="anon-bench")
    os.chdir(work)
    try:
        app = lt.make_app()
        from modules import sleeper

        try:
            from modules import derived_cache
        except ImportError:  # the baseline tree (--dump only) predates the memo
            derived_cache = None

        sleeper.PLAYERS_CACHE_TTL_SECONDS = 10**9
        import httpx

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bench") as c:
                if a.dump:
                    return await dump(c, Path(a.dump))
                if a.profile:
                    return await profile(c, derived_cache, a.profile, a.reps, a.packages)
                return await run(c, derived_cache, a.reps, a.packages)

        result = asyncio.run(go())
    finally:
        redis_proc.terminate()
        shutil.rmtree(work, ignore_errors=True)
    print(json.dumps(result, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=1))
    return 1 if result.get("mismatches") else 0


if __name__ == "__main__":
    raise SystemExit(main())
