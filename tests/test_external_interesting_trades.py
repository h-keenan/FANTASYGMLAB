"""GET /v1/external/trades/interesting: throwaway fixtures only.

The players frame is synthetic (no data/players.db, no data/*.json); the app's
real valuation lens is replaced by a pre-valued frame so the tests pin the
feed logic (candidate rules, evaluator wiring, rotation, dedupe, auth) rather
than today's live values.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from modules import external_interesting_trades as E

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
NOW_MS = NOW.timestamp() * 1000
AUTH = {"Authorization": "Bearer the-real-secret-key"}


def _row(pid, name, pos, age, v, *, market=None, base=None, team="AAA", inj="", status="Active",
         workload="Stable", trend=0.0, prod=6000, opp=6000, news_ms=None, body=""):
    return {
        "player_id": pid, "name": name, "position": pos, "age": float(age), "team": team,
        "dynasty_score": v, "value_score": v, "score": v,
        "market_score": float(market if market is not None else v),
        "v_base": base if base is not None else v,
        "injury_status": inj, "status": status, "injury_body_part": body, "injury_notes": "",
        "workload_trend": workload, "recency_trend": trend, "production_score": prod,
        "opportunity_score": opp, "opportunity_label": "Strong Opportunity", "news_updated": news_ms,
        "valuation_trade_eligible": True, "player_tier": "Star", "years_exp": 3,
    }


def _frame() -> pd.DataFrame:
    rows = []
    # filler depth so the reference roster has real starters at every position
    for pos, top in (("QB", 6000), ("RB", 5600), ("WR", 5800), ("TE", 4200)):
        for i in range(30):
            v = max(300, top - i * 190)
            rows.append(_row(f"{pos}{i}", f"{pos} Filler {i}", pos, 24 + i % 9, v, market=v * 0.98, base=v))
    rows += [
        # buy-low: market far below model, usage rising, young, healthy
        _row("BL1", "Buy Low", "WR", 24, 6400, market=4200, base=6400, workload="Rising", trend=0.22, news_ms=NOW_MS - 86400000),
        # sell-high: old RB, cooling, priced by the market above the model
        _row("SH1", "Old Back", "RB", 31, 5600, market=6200, base=5600, workload="Cooling", trend=-0.2),
        _row("SH2", "Young Replacement", "WR", 22, 5800, market=5900, base=5800),
        # injured: IR knee, young
        _row("IR1", "Hurt Starter", "WR", 25, 5000, market=5000, base=5000, inj="IR", body="Hamstring"),
        _row("IR2", "Healthy Swap", "RB", 28, 5000, market=5000, base=5000),
        # stars for consolidation
        _row("ST1", "Big Star", "RB", 25, 9000, market=9000, base=9000),
        _row("MID1", "Mid One", "WR", 28, 4200, market=4600, base=4200),
        _row("MID2", "Mid Two", "RB", 28, 3900, market=4500, base=3900),
        # SF QB arbitrage pair
        _row("Q1", "Scarce QB", "QB", 27, 7600, market=5000, base=5600),
        _row("W1", "Same Price WR", "WR", 29, 7500, market=7500, base=7500),
        # TEP
        _row("XTE1", "Premium TE", "TE", 26, 6500, market=5000, base=5600),
        _row("W2", "Same Price WR2", "WR", 28, 6400, market=6400, base=6400),
    ]
    df = pd.DataFrame(rows)
    df["v_1qb_ppr"] = df["v_base"]
    df["v_fmt_ppr"] = df["v_base"]
    return df


def _fake_valued(players_df, fmt, lens):
    out = _frame()
    out["player_id"] = out["player_id"].astype(str)
    return out


@pytest.fixture(scope="module")
def ctx():
    mp = pytest.MonkeyPatch()
    mp.setattr(E, "_valued", _fake_valued)
    try:
        yield E.Context(pd.DataFrame({"x": [1]}), "superflex", "tep", NOW)
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def pool(ctx):
    return E.build_candidates(ctx)


def test_builds_items_from_real_evaluator(pool):
    assert pool, "synthetic market should yield tradeable items"
    for it in pool:
        assert it["id"].startswith("it_")
        assert it["type"] in E.TYPES
        assert it["verdict"]["tone"] in E.ADVERTISABLE_TONES
        assert it["verdict"]["band"]  # produced by trade_offer_analyzer
        assert 0 <= it["spice_score"] <= 100
        assert 2 <= len(it["send"]["assets"]) + len(it["receive"]["assets"]) <= 4
        assert it["why"] and len(it["why"]) <= 3
        assert it["balance"]["receive_value"] == it["receive"]["total_value"]
        assert it["share_card"]["path"].endswith(f"format=superflex&lens=tep")
        # nothing private and nothing invented: every player exists in the fixture
        for a in it["send"]["assets"] + it["receive"]["assets"]:
            if a["kind"] == "player":
                assert a["player_id"] in set(_frame()["player_id"])


def test_buy_low_uses_market_gap_and_usage(pool):
    bl = [i for i in pool if i["type"] == E.TYPE_BUY_LOW]
    assert bl and bl[0]["receive"]["assets"][0]["player_id"] == "BL1"
    assert "Usage trend" in " ".join(bl[0]["why"])


def test_stash_requires_real_injury_signal(pool):
    stash = [i for i in pool if i["type"] == E.TYPE_STASH]
    assert stash and all(i["receive"]["assets"][0]["player_id"] == "IR1" for i in stash)
    assert all(a.get("injury_status") != "IR" for i in stash for a in i["send"]["assets"])


def test_pick_items_use_the_apps_pick_curve(pool):
    picks = [a for i in pool if i["type"] == E.TYPE_PICK for s in (i["send"], i["receive"]) for a in s["assets"] if a["kind"] == "pick"]
    for p in picks:
        assert p["value"] in {7600, 6500, 5600, 3800, 3200, 2700}


def test_item_ids_are_stable_and_unique(ctx):
    a, b = E.build_candidates(ctx), E.build_candidates(ctx)
    assert [i["id"] for i in a] == [i["id"] for i in b]
    assert len({i["id"] for i in a}) == len(a)


def test_rotation_is_deterministic_per_day_and_varies_across_days(pool):
    one = [i["id"] for i in E.select_items(pool, now=NOW, limit=6)]
    again = [i["id"] for i in E.select_items(pool, now=NOW + timedelta(hours=5), limit=6)]
    assert one == again
    other_days = {tuple(i["id"] for i in E.select_items(pool, now=NOW + timedelta(days=d), limit=6)) for d in range(1, 6)}
    assert any(day != tuple(one) for day in other_days)


def test_feed_mixes_types_and_never_reuses_a_player(pool):
    items = E.select_items(pool, now=NOW, limit=8)
    assert len({i["type"] for i in items}) >= 3
    ids = [a.get("player_id") for i in items for s in (i["send"], i["receive"]) for a in s["assets"] if a["kind"] == "player"]
    assert len(ids) == len(set(ids))


def test_filters_type_min_spice_and_exclude(pool):
    only = E.select_items(pool, now=NOW, limit=25, types=[E.TYPE_STASH])
    assert only and {i["type"] for i in only} == {E.TYPE_STASH}
    hi = E.select_items(pool, now=NOW, limit=25, min_spice=60)
    assert all(i["spice_score"] >= 60 for i in hi)
    first = E.select_items(pool, now=NOW, limit=3)
    rest = E.select_items(pool, now=NOW, limit=3, exclude_ids=[i["id"] for i in first])
    assert not ({i["id"] for i in first} & {i["id"] for i in rest})


def test_since_suppresses_earlier_days_heads(pool):
    yesterday = NOW - timedelta(days=1)
    head_yesterday = {i["id"] for i in E.select_items(pool, now=yesterday, limit=3)}
    today = {i["id"] for i in E.select_items(pool, now=NOW, limit=3, since=yesterday.date())}
    assert not (head_yesterday & today)


def test_parse_since_accepts_iso_and_epoch_and_rejects_junk():
    assert E.parse_since("2026-10-25T00:00:00Z", NOW) == date(2026, 10, 25)
    assert E.parse_since(str(int(NOW.timestamp()) - 86400), NOW) == date(2026, 10, 26)
    assert E.parse_since("2020-01-01", NOW) == (NOW - timedelta(days=E.MAX_SINCE_DAYS)).date()
    assert E.parse_since(None, NOW) is None
    with pytest.raises(ValueError):
        E.parse_since("yesterday-ish", NOW)


def test_spice_is_transparent_and_bounded(pool):
    for it in pool:
        b = it["spice_breakdown"]
        total = b["star_power"] + b["edge"] + b["story_signal"] + b["newsy"]
        assert abs(min(100, round(total)) - it["spice_score"]) <= 1
        assert b["star_power"] <= 25 and b["edge"] <= 30 and b["story_signal"] <= 30 and b["newsy"] <= 15


def test_upcoming_draft_year():
    assert E.upcoming_draft_year(date(2026, 10, 27)) == 2027
    assert E.upcoming_draft_year(date(2027, 2, 1)) == 2027


def test_reference_roster_is_real_players_only(ctx):
    assert not ctx.baseline.empty
    assert set(ctx.baseline["player_id"]) <= set(_frame()["player_id"])


# ---- HTTP layer -----------------------------------------------------------


@pytest.fixture()
def client(monkeypatch, pool):
    from fastapi.testclient import TestClient
    from services import mobile_api_service

    monkeypatch.setenv("FANTASYDESK_EXTERNAL_API_KEY", "the-real-secret-key")
    monkeypatch.setattr(E, "get_pool", lambda db, fmt, lens, now=None: (pool, 1_790_000_000.0))
    return TestClient(mobile_api_service.app)


@pytest.mark.parametrize("path", ["/v1/external/trades/interesting", "/v1/external/trades/interesting/it_x/share-card.png"])
def test_requires_the_external_api_key(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_endpoint_contract(client):
    r = client.get("/v1/external/trades/interesting", params={"limit": 4}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] and body["format"] == "superflex" and body["lens"] == "ppr"
    assert body["count"] == len(body["items"]) <= 4
    assert body["spice"]["version"] == E.SPICE_VERSION and body["verdict_basis"]
    assert set(body["available_types"]) == set(E.TYPES)
    ids = [i["id"] for i in body["items"]]
    again = client.get("/v1/external/trades/interesting", params={"limit": 4, "exclude_ids": ",".join(ids)}, headers=AUTH).json()
    assert not (set(ids) & {i["id"] for i in again["items"]})


@pytest.mark.parametrize(
    "params",
    [{"format": "2qb"}, {"lens": "half"}, {"type": "nope"}, {"limit": 0}, {"limit": 99}, {"min_spice": 101}, {"since": "soon"}],
)
def test_bad_params_are_422(client, params):
    assert client.get("/v1/external/trades/interesting", params=params, headers=AUTH).status_code == 422


def test_share_card_unknown_id_is_404_and_known_renders_png(client, pool, monkeypatch):
    assert client.get("/v1/external/trades/interesting/it_nope/share-card.png", headers=AUTH).status_code == 404
    from modules import share_card_renderer

    monkeypatch.setattr(share_card_renderer, "render_share_card_png", lambda card: b"\x89PNG-fake")
    iid = pool[0]["id"]
    r = client.get(f"/v1/external/trades/interesting/{iid}/share-card.png", headers=AUTH)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_idea_for_share_card_has_no_private_fields(pool):
    idea = E.idea_for_share_card({k: v for k, v in pool[0].items() if not k.startswith("_")})
    assert set(idea) >= {"send_assets", "receive_assets", "trade_gain"}
    blob = repr(idea).lower()
    assert "token" not in blob and "league_id" not in blob and "roster" not in blob
