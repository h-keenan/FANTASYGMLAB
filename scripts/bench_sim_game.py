#!/usr/bin/env python3
"""Repeatable latency benchmark for the Fantasy Sim GM game API (``/v1/sim/games*``).

Builds full synthetic 12-team games (a redraft at week 8 with seven played weeks of
history, and a dynasty game at season 3 week 8) against the repo's synthetic player pool
and an instrumented in-memory store, then drives the interactive endpoints through the
real FastAPI router and reports, per endpoint:

  * server CPU time p50 / p95 (ASGI receive -> last body byte on the serving thread; handlers
    run inline, so thread-pool scheduling and the test client's JSON parse are excluded, and
    the number stays meaningful on a loaded machine) plus wall p50 for reference. With
    --rtt-ms the modeled production latency is cpu + store_rounds * rtt,
  * store round trips (calls and serial depth: calls that overlap in time are one round),
  * events folded per request, rows/bytes read from the store, response bytes,
  * a phase breakdown (store / fold / view building / evaluator construction),
  * optionally a cProfile top-N for one endpoint.

No network, no real data: never touches data/players.db. Usage::

    python scripts/bench_sim_game.py                       # table to stdout
    python scripts/bench_sim_game.py --json out.json       # machine readable
    python scripts/bench_sim_game.py --only waiver --profile waiver_add
    python scripts/bench_sim_game.py --rtt-ms 35           # add 35 ms to every store call

``--rtt-ms N`` adds N ms to every store call so cached/parallel paths show their real value
against a networked database (Supabase is ~20-60 ms per REST call from the API host).
"""

from __future__ import annotations

import argparse
import cProfile
import copy
import io
import json
import os
import pstats
import statistics
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, Header, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from modules.sim import api as sim_api  # noqa: E402
from modules.sim import game_state, game_store, inputs as sim_inputs, store as sim_store, synthetic  # noqa: E402

ENV_FLAG = sim_api.ENV_FLAG
PlayerPool = sim_inputs.PlayerPool
InMemoryBackend = sim_store.InMemoryBackend
build_synthetic_pool = synthetic.build_synthetic_pool

USER = "bench"
H = {"Authorization": USER}


# --------------------------------------------------------------- instrumentation


class Meter:
    """Per-request accumulators, reset before every request."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.calls: dict[str, int] = defaultdict(int)
        self.intervals: list[tuple[float, float]] = []
        self.rows = 0
        self.bytes = 0
        self.phase: dict[str, float] = defaultdict(float)
        self.events_folded = 0
        self.resp_bytes = 0
        self.server_ms = 0.0
        self.cpu_ms = 0.0

    def serial_depth(self) -> int:
        """Store calls that overlap in time count as one round trip."""

        depth, end = 0, -1.0
        for start, stop in sorted(self.intervals):
            if start >= end:
                depth += 1
                end = stop
            else:
                end = max(end, stop)
        return depth


METER = Meter()


class CountingBackend(InMemoryBackend):
    """InMemoryBackend that counts calls/rows/bytes and can add a fixed per-call RTT."""

    rtt_s = 0.0
    measure_bytes = True

    def _wrap(self, op: str, table: str, fn: Callable[[], Any]) -> Any:
        t0 = time.perf_counter()
        if self.rtt_s:
            time.sleep(self.rtt_s)
        out = fn()
        t1 = time.perf_counter()
        with METER.lock:
            METER.calls[f"{op}:{table}"] += 1
            METER.intervals.append((t0, t1))
        return out

    def select(self, table, **kw):
        rows, err = self._wrap("select", table, lambda: InMemoryBackend.select(self, table, **kw))
        with METER.lock:
            METER.rows += len(rows)
            if self.measure_bytes:
                METER.bytes += len(json.dumps(rows, default=str))
        return rows, err

    def upsert(self, table, row, **kw):
        return self._wrap("upsert", table, lambda: InMemoryBackend.upsert(self, table, row, **kw))

    def update(self, table, **kw):
        return self._wrap("update", table, lambda: InMemoryBackend.update(self, table, **kw))

    def delete(self, table, **kw):
        return self._wrap("delete", table, lambda: InMemoryBackend.delete(self, table, **kw))

    def insert_many(self, table, rows):
        return self._wrap("insert", table, lambda: InMemoryBackend.insert_many(self, table, rows))


def _timed(owner: Any, name: str, bucket: str) -> None:
    orig = getattr(owner, name, None)
    if orig is None:
        return

    def wrapper(*a, **k):
        t0 = time.perf_counter()
        try:
            return orig(*a, **k)
        finally:
            with METER.lock:
                METER.phase[bucket] += time.perf_counter() - t0

    setattr(owner, name, wrapper)


def install_phase_timers() -> None:
    """Inclusive wall time per phase (buckets may nest: load_state includes fold)."""

    from modules.sim import game_ai, game_eval, game_home, game_view

    for name in ("get_game", "get_snapshot", "load_state", "load_events", "latest_checkpoint",
                 "append_events", "touch", "save_checkpoint"):
        _timed(game_store.GameStore, name, f"store.{name}")
    _timed(game_state.GameState, "from_dict", "state.from_dict")
    _timed(game_eval.Evaluator, "__init__", "evaluator.init")
    _timed(game_eval.Evaluator, "best_lineup", "evaluator.best_lineup")
    for fn in ("game_view", "players_page", "league_view", "lineup_view", "team_roster", "inbox_view",
               "pending_claims", "draft_view", "players_for", "player_detail"):
        _timed(game_view, fn, f"view.{fn}")
    for fn in ("home_view", "team_detail"):
        _timed(game_home, fn, f"view.{fn}")
    for fn in ("verdict", "build_counter", "find_deal", "ai_accepts", "utility"):
        _timed(game_ai.TradeDesk, fn, f"trade.{fn}")
    orig_fold = game_store.fold

    def fold(snapshot, events, state):
        t0 = time.perf_counter()
        try:
            return orig_fold(snapshot, events, state)
        finally:
            with METER.lock:
                METER.phase["state.fold"] += time.perf_counter() - t0
                METER.events_folded += len(events)

    game_store.fold = fold


# ---------------------------------------------------------------------- the app


class PoolInputs:
    def __init__(self, mult: int = 1) -> None:
        rows, self.byes = build_synthetic_pool(7)
        self.rows = list(rows)
        for k in range(1, mult):  # a bigger pool: clones with new ids
            for r in rows:
                if r["pos"] == "DEF":
                    continue
                self.rows.append({**r, "pid": f"{r['pid']}x{k}", "name": f"{r['name']} {k}",
                                  "mean": round(r["mean"] * 0.6, 2), "market": round(r["market"] * 0.4, 2)})

    def player_pool(self, scoring):
        return PlayerPool(self.rows, self.byes)


class TimingMiddleware:
    """Pure ASGI: server time = request start -> final body chunk; response bytes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        t0 = time.perf_counter()
        c0 = time.thread_time()
        size = 0

        async def _send(msg):
            nonlocal size
            if msg["type"] == "http.response.body":
                size += len(msg.get("body", b""))
                if not msg.get("more_body"):
                    METER.server_ms = (time.perf_counter() - t0) * 1000.0
                    METER.cpu_ms = (time.thread_time() - c0) * 1000.0
                    METER.resp_bytes = size
            await send(msg)

        await self.app(scope, receive, _send)


def make_app(backend, inputs, *, inline: bool = True):
    def require_user(authorization: str | None = Header(default=None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="no")
        return {"id": authorization, "_access_token": "tok"}

    if inline:  # run sync handlers on the loop thread: no thread-pool noise, and cProfile sees them
        import fastapi.routing as fr

        async def run_inline(func, *a, **k):
            return func(*a, **k)

        fr.run_in_threadpool = run_inline
    app = FastAPI()
    sim_api.mount(app, sim_api.SimApiDeps(
        require_user=require_user, is_pro=lambda u: True, sleeper_username=lambda u: "",
        backend_for=lambda u: backend, inputs=inputs), environ={ENV_FLAG: "1"})
    app.add_middleware(TimingMiddleware)
    return TestClient(app)


class Bench:
    def __init__(self, mult: int = 1, rtt_ms: float = 0.0, measure_bytes: bool = True) -> None:
        self.backend = CountingBackend()
        CountingBackend.rtt_s = 0.0  # set only for measured requests
        CountingBackend.measure_bytes = measure_bytes
        self.rtt_s = rtt_ms / 1000.0
        self.client = make_app(self.backend, PoolInputs(mult))
        self.results: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------ http helpers

    def call(self, method: str, path: str, **kw) -> dict[str, Any]:
        res = self.client.request(method, f"/v1/sim{path}", headers=H, **kw)
        if res.status_code != 200:
            raise RuntimeError(f"{method} {path} -> {res.status_code} {res.text[:300]}")
        return res.json()

    def measured(self, name: str, method: str, path: str, **kw) -> dict[str, Any]:
        METER.reset()
        CountingBackend.rtt_s = self.rtt_s
        t0 = time.perf_counter()
        out = self.call(method, path, **kw)
        wall = (time.perf_counter() - t0) * 1000.0
        CountingBackend.rtt_s = 0.0
        row = {
            "server_ms": METER.server_ms, "cpu_ms": METER.cpu_ms, "wall_ms": wall, "calls": sum(METER.calls.values()),
            "rounds": METER.serial_depth(), "by_call": dict(METER.calls), "rows": METER.rows,
            "store_bytes": METER.bytes, "resp_bytes": METER.resp_bytes, "events": METER.events_folded,
            "phase": {k: v * 1000.0 for k, v in METER.phase.items()},
        }
        self.results.setdefault(name, {"samples": []})["samples"].append(row)
        return out

    # -------------------------------------------------------------- scenarios

    def snapshot_backend(self) -> dict[str, list]:
        return copy.deepcopy(self.backend.tables)

    def restore_backend(self, tables: dict[str, list]) -> None:
        self.backend.tables = copy.deepcopy(tables)

    def build_redraft(self, week: int = 8, user_slot: int = 5) -> str:
        gid = self.call("POST", "/games", json={"user_slot": user_slot, "teams": 12, "team_name": "Bench FC"})["game"]["id"]
        self.call("POST", f"/games/{gid}/draft/auto")
        while self.call("GET", f"/games/{gid}")["game"]["week"] < week:
            self.call("POST", f"/games/{gid}/advance")
        return gid

    def build_dynasty(self, seasons_before: int = 2, week: int = 8) -> str:
        body = {"mode": "dynasty", "teams": 12, "user_slot": 5, "seasons": 5, "rookie_rounds": 3,
                "start_year": 2026, "team_name": "Bench Dynasty"}
        gid = self.call("POST", "/games", json=body)["game"]["id"]
        self.call("POST", f"/games/{gid}/draft/auto")
        for _ in range(seasons_before):
            while True:
                out = self.call("POST", f"/games/{gid}/advance")
                if out["game"]["status"] in ("offseason", "complete"):
                    break
            self.call("POST", f"/games/{gid}/offseason/rookie-draft/start")
            self.call("POST", f"/games/{gid}/offseason/rookie-draft/auto")
            for _ in range(12):
                off = self.call("GET", f"/games/{gid}/offseason")["offseason"]
                if not off["roster"]["cuts_needed"]:
                    break
                roster = self.call("GET", f"/games/{gid}/teams/{self.you(gid)}")["players"]
                worst = sorted(roster, key=lambda p: p["ros_mean"])[0]["id"]
                self.call("POST", f"/games/{gid}/cut", json={"player_id": worst})
            self.call("POST", f"/games/{gid}/offseason/start-season")
        while self.call("GET", f"/games/{gid}")["game"]["week"] < week:
            self.call("POST", f"/games/{gid}/advance")
        return gid

    def you(self, gid: str) -> str:
        return self.call("GET", f"/games/{gid}")["game"]["you"]["team_id"]

    def restore_and_open(self, tables: dict[str, list], gid: str) -> None:
        """Put the store back, then open the game as a user would before acting (that read warms the
        in-process state cache; restoring behind its back is otherwise a deliberate cache miss)."""

        self.restore_backend(tables)
        self.call("GET", f"/games/{gid}")

    # ---------------------------------------------------------------- workloads

    def some_player(self, gid: str) -> str:
        return next(x["player"]["id"] for x in self.call("GET", f"/games/{gid}/lineup")["slots"] if x["player"])

    def run_reads(self, tag: str, gid: str, n: int) -> None:
        you = self.you(gid)
        other = next(t["team_id"] for t in self.call("GET", f"/games/{gid}/league")["teams"] if not t["is_you"])
        for _ in range(n):
            self.measured(f"{tag}:GET game", "GET", f"/games/{gid}")
            self.measured(f"{tag}:GET home", "GET", f"/games/{gid}/home")
            self.measured(f"{tag}:GET team (you)", "GET", f"/games/{gid}/teams/{you}")
            self.measured(f"{tag}:GET team (other)", "GET", f"/games/{gid}/teams/{other}")
            self.measured(f"{tag}:GET players avail p1", "GET", f"/games/{gid}/players?status=available&page_size=25")
            self.measured(f"{tag}:GET players size60", "GET", f"/games/{gid}/players?page_size=60&sort=value")
            self.measured(f"{tag}:GET league", "GET", f"/games/{gid}/league")
            self.measured(f"{tag}:GET lineup", "GET", f"/games/{gid}/lineup")
            self.measured(f"{tag}:GET inbox", "GET", f"/games/{gid}/inbox")
            self.measured(f"{tag}:GET picks", "GET", f"/games/{gid}/picks")
            # Added with the league / history / block / sim-to work (perf audit 2, 2026-11).
            self.measured(f"{tag}:GET league/rosters", "GET", f"/games/{gid}/league/rosters")
            self.measured(f"{tag}:GET player detail", "GET", f"/games/{gid}/players/{self.some_player(gid)}")
            self.measured(f"{tag}:GET player history", "GET", f"/games/{gid}/players/{self.some_player(gid)}/history")
            self.measured(f"{tag}:GET team history", "GET", f"/games/{gid}/teams/{other}/history")
            self.measured(f"{tag}:GET sim-to options", "GET", f"/games/{gid}/sim-to/options")

    def run_waivers(self, tag: str, gid: str, n: int) -> None:
        you = self.you(gid)
        for i in range(n):
            free = self.call("GET", f"/games/{gid}/players?status=available&page_size=40")["items"]
            roster = self.call("GET", f"/games/{gid}/teams/{you}")["players"]
            add, drop = free[i % len(free)]["id"], roster[-1 - (i % 3)]["id"]
            out = self.measured(f"{tag}:POST waivers (add claim)", "POST", f"/games/{gid}/waivers",
                                json={"add": add, "drop": drop})
            cid = out.get("claim_id")
            if cid:
                self.measured(f"{tag}:DELETE waivers/{{id}}", "DELETE", f"/games/{gid}/waivers/{cid}")

    def run_lineup(self, tag: str, gid: str, n: int) -> None:
        for _ in range(n):
            lu = self.call("GET", f"/games/{gid}/lineup")
            slots = [{"slot": s["slot"], "player_id": (s["player"] or {}).get("id")} for s in lu["slots"]]
            self.measured(f"{tag}:PUT lineup", "PUT", f"/games/{gid}/lineup", json={"slots": slots})
            self.measured(f"{tag}:POST lineup/auto", "POST", f"/games/{gid}/lineup/auto")

    def trade_pair(self, gid: str) -> tuple[str, list[str], list[str]]:
        you = self.you(gid)
        mine = self.call("GET", f"/games/{gid}/teams/{you}")["players"]
        league = self.call("GET", f"/games/{gid}/league")["teams"]
        partner = next(t["team_id"] for t in league if not t["is_you"])
        theirs = self.call("GET", f"/games/{gid}/teams/{partner}")["players"]
        return partner, [mine[3]["id"]], [theirs[3]["id"]]

    def run_trades(self, tag: str, gid: str, n: int, base: dict) -> None:
        partner, give, get = self.trade_pair(gid)
        body = {"partner": partner, "give": give, "get": get}
        for _ in range(n):
            self.measured(f"{tag}:POST trades/preview", "POST", f"/games/{gid}/trades/preview", json=body)
        for _ in range(n):  # a send may execute: restore between iterations so every sample is comparable
            self.restore_and_open(base, gid)
            self.measured(f"{tag}:POST trades (send)", "POST", f"/games/{gid}/trades", json=body)
        self.restore_backend(base)

    def run_inbox(self, tag: str, gid: str, n: int, base: dict) -> None:
        if not self.call("GET", f"/games/{gid}/inbox")["items"]:
            return
        for _ in range(n):
            self.restore_and_open(base, gid)
            for action in ("decline", "accept"):
                items = self.call("GET", f"/games/{gid}/inbox")["items"]
                if not items:
                    break
                self.measured(f"{tag}:POST inbox respond ({action})", "POST",
                              f"/games/{gid}/inbox/{items[0]['id']}/respond", json={"action": action})
        self.restore_backend(base)

    def run_cut(self, tag: str, gid: str, n: int, base: dict) -> None:
        you = self.you(gid)
        for _ in range(n):
            self.restore_and_open(base, gid)
            roster = self.call("GET", f"/games/{gid}/teams/{you}")["players"]
            self.measured(f"{tag}:POST cut", "POST", f"/games/{gid}/cut", json={"player_id": roster[-1]["id"]})
        self.restore_backend(base)

    def run_advance(self, tag: str, gid: str, n: int, base: dict) -> None:
        for _ in range(n):
            self.restore_and_open(base, gid)
            self.measured(f"{tag}:POST advance", "POST", f"/games/{gid}/advance")
        self.restore_backend(base)

    def run_draft(self, n: int) -> None:
        for g in self.call("GET", "/games").get("games", []):  # the per-user game cap would refuse a new one
            self.call("DELETE", f"/games/{g['id']}")
        for i in range(n):
            made = self.call("POST", "/games", json={"user_slot": 3 + (i % 5), "teams": 12})
            gid = made["game"]["id"]
            self.measured("draft:GET draft", "GET", f"/games/{gid}/draft")
            self.measured("draft:POST draft/pick", "POST", f"/games/{gid}/draft/pick",
                          json={"player_id": made["hint"]["player"]["id"]})
            self.measured("draft:POST draft/auto", "POST", f"/games/{gid}/draft/auto")
            self.call("DELETE", f"/games/{gid}")

    def sizes(self, gid: str) -> dict[str, int]:
        t = self.backend.tables
        games = [r for r in t["sim_games"] if r["id"] == gid][0]
        cps = [r for r in t.get("sim_week_checkpoints", []) if r["game_id"] == gid]
        events = [r for r in t.get("sim_events", []) if r["game_id"] == gid]
        cps.sort(key=lambda r: r["week"])
        return {
            "snapshot_bytes": len(json.dumps(games["snapshot"])),
            "checkpoint_bytes": len(json.dumps(cps[-1]["state"])) if cps else 0,
            "events_total": len(events),
            "events_bytes": len(json.dumps([e["payload"] for e in events])),
            "events_after_checkpoint": sum(1 for e in events if cps and e["seq"] >= cps[-1]["event_seq"]),
        }

    def concurrency(self, gid: str, threads: int = 8) -> dict[str, float]:
        """Parallel readers of one game: how long does the slowest wait?"""

        out: list[float] = []
        t0 = time.perf_counter()

        def work():
            self.client.get(f"/v1/sim/games/{gid}/home", headers=H).raise_for_status()
            out.append(time.perf_counter() - t0)

        ts = [threading.Thread(target=work) for _ in range(threads)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        return {"threads": threads, "max_ms": round(max(out) * 1000, 1), "min_ms": round(min(out) * 1000, 1)}


# ---------------------------------------------------------------------- report


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def summarize(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for name, data in results.items():
        s = data["samples"]
        ms = [x["cpu_ms"] for x in s]
        phases: dict[str, float] = defaultdict(float)
        for x in s:
            for k, v in x["phase"].items():
                phases[k] += v / len(s)
        rows.append({
            "name": name, "n": len(s), "p50_ms": pct(ms, 0.5), "p95_ms": pct(ms, 0.95),
            "wall_p50_ms": pct([x["server_ms"] for x in s], 0.5),
            "store_calls": statistics.median(x["calls"] for x in s),
            "store_rounds": statistics.median(x["rounds"] for x in s),
            "store_rows": statistics.median(x["rows"] for x in s),
            "store_kb": statistics.median(x["store_bytes"] for x in s) / 1024,
            "events_folded": statistics.median(x["events"] for x in s),
            "resp_kb": statistics.median(x["resp_bytes"] for x in s) / 1024,
            "by_call": s[len(s) // 2]["by_call"],
            "phase_ms": dict(sorted(((k, round(v, 2)) for k, v in phases.items()), key=lambda kv: -kv[1])),
        })
    return rows


def print_table(rows: list[dict[str, Any]], detail: bool) -> None:
    print(f"{'endpoint':46} {'n':>3} {'cpu p50':>8} {'cpu p95':>8} {'wall p50':>8} {'calls':>5} {'rounds':>6} {'events':>6} {'storeKB':>8} {'respKB':>8}")
    for r in rows:
        print(f"{r['name']:46} {r['n']:>3} {r['p50_ms']:8.1f} {r['p95_ms']:8.1f} {r['wall_p50_ms']:8.1f} {r['store_calls']:5.0f} "
              f"{r['store_rounds']:6.0f} {r['events_folded']:6.0f} {r['store_kb']:8.1f} {r['resp_kb']:8.1f}")
        if detail:
            print("      calls:", r["by_call"])
            print("      phase_ms:", r["phase_ms"])


def profile_one(bench: Bench, gid: str, which: str, base: dict) -> None:
    prof = cProfile.Profile()
    you = bench.you(gid)
    free = bench.call("GET", f"/games/{gid}/players?status=available&page_size=5")["items"]
    roster = bench.call("GET", f"/games/{gid}/teams/{you}")["players"]
    partner, give, get = bench.trade_pair(gid)
    plan = {
        "waiver_add": ("POST", f"/games/{gid}/waivers", {"json": {"add": free[0]["id"], "drop": roster[-1]["id"]}}),
        "home": ("GET", f"/games/{gid}/home", {}),
        "players": ("GET", f"/games/{gid}/players?status=available&page_size=25", {}),
        "league": ("GET", f"/games/{gid}/league", {}),
        "trade_preview": ("POST", f"/games/{gid}/trades/preview", {"json": {"partner": partner, "give": give, "get": get}}),
        "trade_send": ("POST", f"/games/{gid}/trades", {"json": {"partner": partner, "give": give, "get": get}}),
        "advance": ("POST", f"/games/{gid}/advance", {}),
        "lineup_auto": ("POST", f"/games/{gid}/lineup/auto", {}),
    }
    method, path, kw = plan[which]
    for _ in range(3):  # warm
        bench.restore_and_open(base, gid)
        bench.call(method, path, **kw)
    for _ in range(5):
        bench.restore_and_open(base, gid)  # (not profiled)
        prof.enable()
        bench.call(method, path, **kw)
        prof.disable()
    out = io.StringIO()
    pstats.Stats(prof, stream=out).sort_stats("tottime").print_stats(20)
    print(f"\n=== cProfile (top 20 by self time over 5 calls; the in-memory store's row copies and the test client stand in for network + JSON) for {which} ===")
    print(out.getvalue()[:7000])
    bench.restore_backend(base)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=12, help="samples per endpoint")
    ap.add_argument("--only", default="", help="comma list: reads,waiver,lineup,trade,inbox,cut,advance,draft")
    ap.add_argument("--scenario", default="redraft,dynasty", help="redraft and/or dynasty")
    ap.add_argument("--pool-mult", type=int, default=1, help="multiply the synthetic pool size")
    ap.add_argument("--rtt-ms", type=float, default=0.0, help="simulated store round-trip per call")
    ap.add_argument("--fixture", default="", help="pickle of pre-built games: loaded if present, else built and saved "
                    "(identical saves let two code versions be compared on the very same event logs)")
    ap.add_argument("--json", default="")
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--profile", default="", help="cProfile one of: waiver_add,home,players,league,trade_preview,trade_send,advance,lineup_auto")
    args = ap.parse_args()
    groups = set(filter(None, args.only.split(","))) or {"reads", "waiver", "lineup", "trade", "inbox", "cut", "advance", "draft"}

    install_phase_timers()
    bench = Bench(args.pool_mult, args.rtt_ms)
    meta: dict[str, Any] = {"pool_mult": args.pool_mult, "rtt_ms": args.rtt_ms, "n": args.n}
    scenarios = set(args.scenario.split(","))
    fixture: dict[str, Any] = {}
    if args.fixture and Path(args.fixture).exists():
        import pickle

        fixture = pickle.loads(Path(args.fixture).read_bytes())
        bench.backend.tables = fixture["tables"]
    for tag, build in (("redraft w8", bench.build_redraft), ("dynasty s3 w8", bench.build_dynasty)):
        if tag.split()[0] not in scenarios:
            continue
        t0 = time.time()
        gid = fixture.get("gids", {}).get(tag)
        if gid is None:
            gid = build()
            fixture.setdefault("gids", {})[tag] = gid
            if args.fixture:
                import pickle

                fixture["tables"] = copy.deepcopy(bench.backend.tables)
                Path(args.fixture).write_bytes(pickle.dumps(fixture))
        meta[f"build_s[{tag}]"] = round(time.time() - t0, 1)
        meta[f"sizes[{tag}]"] = bench.sizes(gid)
        base = bench.snapshot_backend()
        if "reads" in groups:
            bench.run_reads(tag, gid, max(3, args.n // 2))
        if "waiver" in groups:
            bench.run_waivers(tag, gid, args.n)
        if "lineup" in groups:
            bench.run_lineup(tag, gid, args.n)
        base = bench.snapshot_backend()
        if "trade" in groups:
            bench.run_trades(tag, gid, args.n, base)
        if "inbox" in groups:
            bench.run_inbox(tag, gid, max(3, args.n // 3), base)
        if "cut" in groups:
            bench.run_cut(tag, gid, max(3, args.n // 2), base)
        if "advance" in groups:
            bench.run_advance(tag, gid, max(3, args.n // 3), base)
        meta[f"concurrency[{tag}]"] = bench.concurrency(gid)
        if args.profile:
            profile_one(bench, gid, args.profile, base)
    if "draft" in groups and "redraft" in scenarios:
        bench.run_draft(max(3, args.n // 3))

    rows = summarize(bench.results)
    print_table(rows, args.detail)
    print("\nmeta:", json.dumps(meta, indent=1))
    if args.json:
        Path(args.json).write_text(json.dumps({"meta": meta, "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
