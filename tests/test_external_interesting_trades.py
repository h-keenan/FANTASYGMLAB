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


def test_since_filters_on_generated_at_not_rotation_history(pool):
    """Regression: a 14-day epoch `since` used to return 0 items. It skipped
    the top-`limit` of every UTC day's rotation back 14 days (14 x limit ids,
    more than the pool), so a bot polling with since=<14 days ago> got nothing
    while the same query without `since` returned items."""

    baseline = [i["id"] for i in E.select_items(pool, now=NOW, limit=5)]
    assert baseline
    for raw in (str(int(NOW.timestamp()) - 14 * 86400), str(int(NOW_MS) - 14 * 86400 * 1000),
                (NOW - timedelta(days=14)).isoformat(), "2020-01-01"):
        since = E.parse_since(raw, NOW)
        assert [i["id"] for i in E.select_items(pool, now=NOW, limit=5, since=since)] == baseline, raw


def test_since_future_cutoff_returns_nothing_and_cutoff_is_inclusive(pool):
    assert E.select_items(pool, now=NOW, limit=5, since=NOW + timedelta(seconds=1)) == []
    assert E.select_items(pool, now=NOW, limit=5, since=NOW)


def test_parse_since_accepts_iso_epoch_seconds_and_millis_and_rejects_junk():
    day_ago = NOW - timedelta(days=1)
    assert E.parse_since("2026-10-25T00:00:00Z", NOW) == datetime(2026, 10, 25, tzinfo=timezone.utc)
    assert E.parse_since("2026-10-25", NOW) == datetime(2026, 10, 25, tzinfo=timezone.utc)
    assert E.parse_since(str(int(day_ago.timestamp())), NOW) == day_ago
    assert E.parse_since(str(int(day_ago.timestamp() * 1000)), NOW) == day_ago
    assert E.parse_since("2020-01-01", NOW) == NOW - timedelta(days=E.MAX_SINCE_DAYS)
    assert E.parse_since(None, NOW) is None and E.parse_since("  ", NOW) is None
    for bad in ("yesterday-ish", "99999999999999999999999"):
        with pytest.raises(ValueError):
            E.parse_since(bad, NOW)


def test_free_text_numbers_come_from_structured_fields(pool):
    assert pool
    for it in pool:
        assert E.unreconciled_numbers(it) == [], (it["id"], it["hook"], it["why"])
        assert it["text_figures"] is not None


def test_number_scan_catches_a_drifted_number(pool):
    it = dict(pool[0])
    it["why"] = [*it["why"], "He is worth 12,345 in this deal."]
    assert E.unreconciled_numbers(it) == ["12,345"]


def test_buy_low_hook_and_why_share_one_market_price(pool):
    it = next(i for i in pool if i["type"] == E.TYPE_BUY_LOW)
    price = f"{int(it['text_figures']['market_price']):,}"
    assert price in it["hook"] and price in it["why"][0]
    assert f"{it['receive']['assets'][0]['value']:,}" in it["hook"]
    assert f"{it['send']['assets'][0]['value']:,}" in it["why"][2]


def test_share_card_descriptor_contract(pool):
    sc = pool[0]["share_card"]
    assert (sc["width"], sc["height"]) == (1600, 1600)
    assert sc["brand"] == "FantasyDesk" and sc["destination"] == "https://fantasydesk.app"
    assert sc["content_type"] == "image/png" and sc["available"] and sc["path"].startswith("/v1/external/")
    assert sc["safe_area"] == {"margin_pct": 8, "x": 128, "y": 128, "width": 1344, "height": 1344}
    assert sc["focus"] == {"x": 0.5, "y": 0.5}


def test_square_card_is_1600_fantasydesk_and_inside_safe_area(pool):
    from io import BytesIO

    from PIL import Image

    from modules import share_card_renderer, share_card_qr, share_recommendation_cards

    card = share_recommendation_cards.build_trade_share_card(
        E.idea_for_share_card({k: v for k, v in pool[0].items() if not k.startswith("_")}),
        source_surface="external_trades", scoring_format="PPR", my_team_name="Team A",
    )
    png = share_card_renderer.render_square_share_card_png(card, destination=E.SHARE_CARD_DESTINATION, portraits={})
    img = Image.open(BytesIO(png)).convert("RGB")
    assert img.size == (1600, 1600)
    # nothing but background outside the 8% safe margins
    bg = img.getpixel((0, 0))
    sa = share_card_renderer.square_safe_area()
    for box in ((0, 0, 1600, sa["y"]), (0, 1600 - sa["y"], 1600, 1600), (0, 0, sa["x"], 1600), (1600 - sa["x"], 0, 1600, 1600)):
        region = img.crop(box)
        assert region.getextrema() == tuple((c, c) for c in bg), box
    # the QR encodes fantasydesk.app, never the legacy domain
    assert share_card_qr.FANTASYDESK_TRACKED_URL.startswith("https://fantasydesk.app/")
    assert "fantasygmlab" not in share_card_qr.FANTASYDESK_TRACKED_URL


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

    seen = {}
    monkeypatch.setattr(share_card_renderer, "render_square_share_card_png", lambda card, **kw: seen.update(kw) or b"\x89PNG-fake")
    iid = pool[0]["id"]
    r = client.get(f"/v1/external/trades/interesting/{iid}/share-card.png", headers=AUTH)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert seen == {"size": 1600, "destination": "https://fantasydesk.app"}


def test_endpoint_14_day_epoch_since_returns_what_no_since_returns(client):
    base = client.get("/v1/external/trades/interesting", params={"limit": 4}, headers=AUTH).json()
    assert base["count"] > 0 and base["since_applied"] is None
    import time
    for since in (str(int(time.time()) - 14 * 86400), str((int(time.time()) - 14 * 86400) * 1000)):
        r = client.get("/v1/external/trades/interesting", params={"limit": 4, "since": since}, headers=AUTH).json()
        assert r["count"] == base["count"] and r["since_applied"]


def test_idea_for_share_card_has_no_private_fields(pool):
    idea = E.idea_for_share_card({k: v for k, v in pool[0].items() if not k.startswith("_")})
    assert set(idea) >= {"send_assets", "receive_assets", "trade_gain"}
    blob = repr(idea).lower()
    assert "token" not in blob and "league_id" not in blob and "roster" not in blob
