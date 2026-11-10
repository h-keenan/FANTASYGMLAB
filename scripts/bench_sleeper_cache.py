"""Local before/after benchmark for modules.sleeper_cache (shared Sleeper cache).

Counts upstream Sleeper requests when several uvicorn-style worker PROCESSES,
each running many request THREADS, all open the same few leagues at once. A
local stub HTTP server stands in for Sleeper (30 ms latency, counts hits); a
throwaway redis-server is shared by the workers. Nothing touches data/ or any
real service.

  python scripts/bench_sleeper_cache.py [--workers 4 --threads 16 --leagues 5]

``legacy`` reproduces the previous behavior (per-process lru_cache only, no
single-flight); ``shared`` is the current code path.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUB_PORT, REDIS_PORT = 18710, 18711
LATENCY_S = 0.03


class _Stub(BaseHTTPRequestHandler):
    hits = 0
    lock = threading.Lock()

    def log_message(self, *a):
        pass

    def do_GET(self):
        with _Stub.lock:
            _Stub.hits += 1
        time.sleep(LATENCY_S)
        if self.path == "/__hits":
            body = json.dumps({"hits": _Stub.hits - 1}).encode()
        else:
            body = json.dumps([{"roster_id": 1, "players": ["1", "2"]}]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _worker(mode: str, threads: int, leagues: int, rounds: int, barrier) -> None:
    sys.path.insert(0, str(ROOT))
    os.environ["REDIS_URL"] = f"redis://127.0.0.1:{REDIS_PORT}/0"
    os.environ["SLEEPER_REQUEST_MAX_RETRIES"] = "0"
    from modules import sleeper

    sleeper.SLEEPER_BASE = f"http://127.0.0.1:{STUB_PORT}"
    if mode == "legacy":
        sleeper._live_league_json = lambda label, url: sleeper._request_json(label, url, timeout=5)

    def hit(i: int) -> None:
        for r in range(rounds):
            sleeper.get_rosters(f"L{(i + r) % leagues}")
            sleeper.get_users(f"L{(i + r) % leagues}")

    barrier.wait()
    ts = [threading.Thread(target=hit, args=(i,)) for i in range(threads)]
    [t.start() for t in ts]
    [t.join() for t in ts]


def run(mode: str, workers: int, threads: int, leagues: int, rounds: int) -> dict:
    redis_dir = tempfile.mkdtemp(prefix="bench-redis-")
    redis = subprocess.Popen(
        ["redis-server", "--port", str(REDIS_PORT), "--save", "", "--appendonly", "no", "--dir", redis_dir],
        stdout=subprocess.DEVNULL,
    )
    import redis as _redis

    for _ in range(100):
        try:
            _redis.Redis(port=REDIS_PORT).ping()
            break
        except Exception:
            time.sleep(0.1)
    _Stub.hits = 0
    server = ThreadingHTTPServer(("127.0.0.1", STUB_PORT), _Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(workers)
    started = time.perf_counter()
    procs = [ctx.Process(target=_worker, args=(mode, threads, leagues, rounds, barrier)) for _ in range(workers)]
    [p.start() for p in procs]
    [p.join() for p in procs]
    wall = time.perf_counter() - started
    hits = _Stub.hits
    server.shutdown()
    redis.terminate()
    redis.wait()
    shutil.rmtree(redis_dir, ignore_errors=True)
    requests_made = workers * threads * rounds * 2
    return {"mode": mode, "cache_lookups": requests_made, "upstream_sleeper_calls": hits, "wall_s": round(wall, 2)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--leagues", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()
    for mode in ("legacy", "shared"):
        print(json.dumps(run(mode, a.workers, a.threads, a.leagues, a.rounds)))


if __name__ == "__main__":
    main()
