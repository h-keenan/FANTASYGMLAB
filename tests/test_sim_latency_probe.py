"""API latency and payload budgets for the GM game, measured through the real FastAPI app (in-memory store).

    python -m tests.test_sim_latency_probe          # prints a table, cold (caches dropped) and warm, at season 1 and week 8
The pytest below is a loose budget guard (warm reads and payload sizes), not a benchmark."""

from __future__ import annotations

import json

from modules.sim.calibration import dataset, tail_report

def latency() -> dict:
    """Wall time and payload size of the phone-facing endpoints through the real FastAPI app (in-memory store), cold (caches
    dropped: what a first request after a deploy or an evicted game costs) and warm, at the start, mid-season and the first offseason."""

    import time

    from fastapi import FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient

    from modules.sim import api as sim_api
    from modules.sim import game_api
    from modules.sim.game_store import SNAPSHOTS, STATES
    from modules.sim.inputs import PlayerPool
    from modules.sim.store import InMemoryBackend

    rows, byes = tail_report.pool_from_panel(dataset.load_panel())

    class PoolInputs:
        def player_pool(self, scoring):
            return PlayerPool(rows, byes)

    backend = InMemoryBackend()

    def require_user(authorization: str | None = Header(default=None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="no")
        return {"id": authorization, "_access_token": "tok"}

    app = FastAPI()
    sim_api.mount(app, sim_api.SimApiDeps(require_user=require_user, is_pro=lambda u: True, sleeper_username=lambda u: "",
                                          backend_for=lambda u: backend, inputs=PoolInputs()), environ={"SIM_ENABLED": "1"})
    client = TestClient(app)
    h = {"Authorization": "pro"}
    game_api.clear_pool_cache()
    out: dict[str, Any] = {}
    res = client.post("/v1/sim/games", json={"mode": "dynasty", "teams": 12, "seasons": 5, "rookie_rounds": 3, "user_slot": 4, "scoring": "ppr"}, headers=h)
    gid = res.json()["game"]["id"]
    base = f"/v1/sim/games/{gid}"

    def timed(method, path, body=None):
        t0 = time.perf_counter()
        r = client.request(method, base + path, json=body, headers=h)
        return round((time.perf_counter() - t0) * 1000, 1), len(r.content), r.status_code

    def cold():
        STATES.drop(gid)
        SNAPSHOTS.drop(gid)

    def probe(label):
        user_team = client.get(base, headers=h).json()["game"]["settings"]["user_slot"]
        reads = ["", "/home", "/lineup", "/league", "/league/rosters", "/players", "/players?pos=WR&sort=value&page=3", "/teams/2", "/inbox", "/picks", "/dynasty"]
        table = {}
        for path in reads:
            cold()
            c = timed("GET", path)
            w = min(timed("GET", path)[0] for _ in range(3))
            table[path or "/"] = {"cold_ms": c[0], "warm_ms": w, "bytes": c[1], "status": c[2]}
        out[label] = table

    client.post(base + "/draft/auto", headers=h)
    probe("season1_week1")
    for _ in range(7):
        client.post(base + "/advance", headers=h)
    probe("season1_week8")
    writes = {}
    for name, (method, path, body) in {"advance": ("POST", "/advance", None), "sim_to_4_weeks": ("POST", "/sim-to", {"target": "weeks", "weeks": 4, "auto_set": True}),
                                       "lineup_auto": ("POST", "/lineup/auto", None)}.items():
        cold()
        writes[name] = timed(method, path, body)[:2]
    out["writes_ms_bytes"] = writes
    client.post(base + "/sim-to", json={"target": "season_end"}, headers=h)
    probe("season1_offseason")
    return out




def test_warm_reads_and_payloads_stay_inside_the_phone_budget():
    out = latency()
    for label in ("season1_week1", "season1_week8"):
        for path, row in out[label].items():
            assert row["status"] == 200, (label, path)
            assert row["warm_ms"] < 400, (label, path, row)
            assert row["bytes"] < 200_000, (label, path, row)  # league/rosters is the heaviest at about 130 KB


if __name__ == "__main__":
    print(json.dumps(latency(), indent=1))
