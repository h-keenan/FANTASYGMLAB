"""League Storylines v1 — deterministic activity intelligence on History data."""

from __future__ import annotations

from pathlib import Path

from modules import league_history as history
from modules import league_storylines as storylines
from modules import league_storylines_ui
from modules.app_styles import APP_CSS
from modules.league_storylines_styles import LEAGUE_STORYLINES_CSS
from modules.ui_architecture import PLATFORM_DESTINATIONS


ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    "1": {"team_name": "War Room", "username": "alpha", "owner_name": "Alpha", "avatar_url": ""},
    "2": {"team_name": "Lakefront", "username": "beta", "owner_name": "Beta", "avatar_url": ""},
    "3": {"team_name": "Northside", "username": "gamma", "owner_name": "Gamma", "avatar_url": ""},
}
PLAYERS = {
    "p1": {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN"},
    "p2": {"name": "Breece Hall", "position": "RB", "team": "NYJ"},
    "p3": {"name": "Trey McBride", "position": "TE", "team": "ARI"},
}


def _tx(**kwargs):
    payload = {
        "status": "complete",
        "roster_ids": [1, 2],
        "adds": {},
        "drops": {},
        "draft_picks": [],
        "status_updated": 1_700_000_000_000,
        "_history_week": 4,
    }
    payload.update(kwargs)
    return payload


def _normalized(rows, *, season="2026", league_id="L-now"):
    return history.normalize_season_payload(
        {"league_id": league_id, "season": season, "transactions": rows},
        profiles=PROFILES,
        player_lookup=PLAYERS,
    )


def _logo(url, name, css_class="dg-lh-logo"):
    return f"<div class='{css_class}'>{name[:2]}</div>"


def test_most_active_and_trade_market_leader():
    rows = [
        _tx(transaction_id="t1", type="trade", adds={"p1": 2, "p2": 1}, _history_week=1),
        _tx(transaction_id="t2", type="trade", adds={"p3": 1}, roster_ids=[1, 2], _history_week=2),
        _tx(
            transaction_id="w1",
            type="waiver",
            roster_ids=[1],
            adds={"p3": 1},
            settings={"waiver_bid": 12},
            _history_week=3,
        ),
        _tx(transaction_id="f1", type="free_agent", roster_ids=[2], adds={"p2": 2}, _history_week=3),
        _tx(
            transaction_id="w2",
            type="waiver",
            roster_ids=[1],
            adds={"p1": 1},
            settings={"waiver_bid": 2},
            _history_week=5,
        ),
    ]
    txs = _normalized(rows)
    activity = storylines.transaction_activity_by_roster(txs)
    assert activity[1]["total"] == 4
    assert activity[1]["trade"] == 2
    assert activity[1]["waiver"] == 2
    assert activity[2]["total"] == 3
    report = storylines.build_league_storylines(txs, profiles=PROFILES, season="2026")
    assert report["most_active"]["team_name"] == "War Room"
    assert report["most_active"]["metric"] == 4
    assert report["most_active"]["breakdown"]["trade"] == 2
    assert report["trade_market_leader"]["metric"] == 2
    html = league_storylines_ui.storylines_panel_html(
        report, team_logo_html=_logo, season="2026"
    )
    assert "Who is driving league activity?" in html
    assert "Who is driving the trade market?" in html
    assert "winner" not in html.casefold()
    assert "fleeced" not in html.casefold()
    assert "best move" not in html.casefold()


def test_biggest_trade_players_and_picks():
    txs = _normalized(
        [
            _tx(
                transaction_id="small",
                type="trade",
                adds={"p1": 2},
                _history_week=1,
            ),
            _tx(
                transaction_id="big",
                type="trade",
                adds={"p1": 1, "p2": 2, "p3": 1},
                draft_picks=[
                    {"season": "2027", "round": 1, "owner_id": 2, "previous_owner_id": 1},
                    {"season": "2028", "round": 2, "owner_id": 1, "previous_owner_id": 2},
                ],
                _history_week=6,
                status_updated=1_710_000_000_000,
            ),
        ]
    )
    biggest = storylines.largest_trade(txs)
    assert biggest["assets"] == 5
    assert biggest["players"] == 3
    assert biggest["picks"] == 2
    assert biggest["week"] == 6
    html = league_storylines_ui.storylines_panel_html(
        storylines.build_league_storylines(txs, profiles=PROFILES),
        team_logo_html=_logo,
    )
    assert "Biggest Trade" in html
    assert "3 players" in html
    assert "2 picks" in html


def test_biggest_faab_and_no_faab_omitted():
    with_faab = _normalized(
        [
            _tx(
                transaction_id="w-low",
                type="waiver",
                roster_ids=[2],
                adds={"p2": 2},
                settings={"waiver_bid": 5},
                _history_week=2,
            ),
            _tx(
                transaction_id="w-high",
                type="waiver",
                roster_ids=[1],
                adds={"p3": 1},
                settings={"waiver_bid": 47},
                _history_week=8,
            ),
        ]
    )
    spend = storylines.biggest_faab_spend(with_faab)
    assert spend["amount"] == 47
    assert spend["team_name"] == "War Room"
    assert spend["player"]["name"] == "Trey McBride"
    html = league_storylines_ui.storylines_panel_html(
        storylines.build_league_storylines(with_faab, profiles=PROFILES),
        team_logo_html=_logo,
    )
    assert "$47" in html
    assert "Biggest FAAB" in html

    no_faab = _normalized(
        [_tx(transaction_id="w0", type="waiver", roster_ids=[1], adds={"p1": 1})]
    )
    assert storylines.biggest_faab_spend(no_faab) is None
    html_none = league_storylines_ui.storylines_panel_html(
        storylines.build_league_storylines(no_faab, profiles=PROFILES),
        team_logo_html=_logo,
    )
    assert "Biggest FAAB" not in html_none


def test_most_picks_acquired_is_historical_not_ownership():
    txs = _normalized(
        [
            _tx(
                transaction_id="t-picks",
                type="trade",
                adds={"p1": 2},
                draft_picks=[
                    {"season": "2027", "round": 1, "owner_id": 1, "previous_owner_id": 2},
                    {"season": "2027", "round": 2, "owner_id": 1, "previous_owner_id": 2},
                    {"season": "2028", "round": 1, "owner_id": 2, "previous_owner_id": 1},
                ],
            )
        ]
    )
    counts = storylines.incoming_pick_count_by_roster(txs)
    assert counts[1] == 2
    assert counts[2] == 1
    report = storylines.build_league_storylines(txs, profiles=PROFILES)
    assert report["most_picks_acquired"]["team_name"] == "War Room"
    assert report["most_picks_acquired"]["metric"] == 2
    html = league_storylines_ui.storylines_panel_html(report, team_logo_html=_logo)
    assert "not current ownership" in html
    assert "dg-mg-stack" in html


def test_roster_turnover_does_not_double_count_same_player_add_drop():
    txs = _normalized(
        [
            _tx(
                transaction_id="w-swap",
                type="waiver",
                roster_ids=[1],
                adds={"p1": 1},
                drops={"p2": 1},
            ),
            _tx(
                transaction_id="same",
                type="free_agent",
                roster_ids=[2],
                adds={"p3": 2},
                drops={"p3": 2},
            ),
        ]
    )
    turnover = storylines.roster_turnover(txs)
    assert turnover[1] == 2
    assert turnover[2] == 1
    report = storylines.build_league_storylines(txs, profiles=PROFILES)
    assert report["roster_turnover"]["team_name"] == "War Room"


def test_ties_are_deterministic_by_team_name():
    txs = _normalized(
        [
            _tx(transaction_id="t-a", type="trade", adds={"p1": 2, "p2": 1}),
            _tx(
                transaction_id="w-a",
                type="waiver",
                roster_ids=[1],
                adds={"p3": 1},
                settings={"waiver_bid": 3},
            ),
            _tx(
                transaction_id="w-b",
                type="waiver",
                roster_ids=[2],
                adds={"p2": 2},
                settings={"waiver_bid": 3},
            ),
        ]
    )
    activity = storylines.transaction_activity_by_roster(txs)
    assert activity[1]["total"] == activity[2]["total"] == 2
    report = storylines.build_league_storylines(txs, profiles=PROFILES)
    assert report["most_active"]["team_name"] == "Lakefront"
    assert report["most_active"]["tied"] is True


def test_no_trades_and_empty_history():
    waivers_only = _normalized(
        [
            _tx(
                transaction_id="w1",
                type="waiver",
                roster_ids=[1],
                adds={"p1": 1},
                settings={"waiver_bid": 9},
            )
        ]
    )
    report = storylines.build_league_storylines(waivers_only, profiles=PROFILES)
    assert report["largest_trade"] is None
    assert report["trade_market_leader"] is None
    assert report["most_picks_acquired"] is None
    html = league_storylines_ui.storylines_panel_html(report, team_logo_html=_logo)
    assert "Biggest Trade" not in html
    assert "Most Active" in html

    empty = storylines.build_league_storylines([], profiles=PROFILES, season="2025")
    empty_html = league_storylines_ui.storylines_panel_html(
        empty, team_logo_html=_logo, season="2025"
    )
    assert "Not enough completed activity" in empty_html


def test_prior_season_and_malformed_transaction():
    prior = _normalized(
        [_tx(transaction_id="old", type="trade", adds={"p1": 2}, _history_week=12)],
        season="2025",
        league_id="L-25",
    )
    report = storylines.build_league_storylines(prior, profiles=PROFILES, season="2025")
    assert report["season"] == "2025"
    assert report["most_active"]["metric"] == 1
    assert history.normalize_transaction(
        {"type": "nope", "status": "complete"},
        league_id="L",
        season="2025",
        week=1,
        profiles=PROFILES,
        player_lookup=PLAYERS,
    ) is None
    skipped = storylines.build_league_storylines(
        [{"type": "trade", "status": "failed", "transaction_id": "x", "sides": []}],
        profiles=PROFILES,
    )
    assert skipped["most_active"] is None


def test_quietest_busiest_week_and_most_moved_player():
    rows = []
    for index in range(3):
        rows.append(
            _tx(
                transaction_id=f"t{index}",
                type="trade",
                adds={"p1": 2},
                _history_week=7,
                status_updated=1_700_000_000_000 + index,
            )
        )
    rows.append(
        _tx(
            transaction_id="solo",
            type="free_agent",
            roster_ids=[1],
            adds={"p3": 1},
            _history_week=2,
        )
    )
    txs = _normalized(rows)
    report = storylines.build_league_storylines(txs, profiles=PROFILES, season="2026")
    assert report["quietest"]["team_name"] == "Northside"
    assert report["quietest"]["metric"] == 0
    assert report["busiest_week"]["week"] == 7
    assert report["busiest_week"]["count"] == 3
    assert report["most_traded_player"]["count"] == 3
    assert report["most_traded_player"]["player"]["name"] == "Ja'Marr Chase"


def test_cache_reuse_and_no_provider_or_top_level_route():
    calls = {"n": 0}

    def fetch_league(_league_id):
        return {"season": "2026", "settings": {"leg": 1}}

    def fetch_transactions(_league_id, week):
        calls["n"] += 1
        return [
            _tx(transaction_id="t1", type="trade", adds={"p1": 2, "p2": 1}, _history_week=week)
        ]

    payload = history.collect_season_transactions(
        "L-now", fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )
    first = calls["n"]
    normalized = history.normalize_season_payload(
        payload, profiles=PROFILES, player_lookup=PLAYERS
    )
    storylines.build_league_storylines(normalized, profiles=PROFILES, season="2026")
    storylines.build_league_storylines(normalized, profiles=PROFILES, season="2026")
    assert calls["n"] == first
    domain = (ROOT / "modules" / "league_storylines.py").read_text(encoding="utf-8")
    assert "get_transactions(" not in domain
    assert "st.rerun" not in domain
    ui = (ROOT / "modules" / "league_storylines_ui.py").read_text(encoding="utf-8")
    assert "st.rerun" not in ui
    assert "winner" not in ui.casefold()
    keys = {page.key for page in PLATFORM_DESTINATIONS}
    assert "storylines" not in keys
    assert LEAGUE_STORYLINES_CSS not in APP_CSS
    assert "@media (max-width:430px)" in LEAGUE_STORYLINES_CSS
    assert "max-width:48rem" in LEAGUE_STORYLINES_CSS
    history_ui = (ROOT / "modules" / "league_history_ui.py").read_text(encoding="utf-8")
    assert "league_storylines_ui.render_storylines_panel(" in history_ui
    assert history_ui.index("cached_season_history_payload(") < history_ui.index(
        "render_storylines_panel("
    )
    assert history_ui.index("render_storylines_panel(") < history_ui.index(
        "filter_history("
    )


def test_unknown_roster_and_malformed_pick_stay_anonymous():
    txs = [
        {
            "transaction_id": "ghost",
            "type": "trade",
            "week": 3,
            "timestamp": 1,
            "roster_ids": [99],
            "sides": [
                {
                    "roster_id": 99,
                    "team_name": "Team 99",
                    "owner_handle": "",
                    "avatar_url": "",
                    "receives": [],
                }
            ],
            "adds": [{"kind": "player", "player_id": "p1", "name": "Ja'Marr Chase", "roster_id": 99}],
            "drops": [],
            "draft_picks": [{"kind": "pick", "label": "broken", "to_roster_id": 0}],
        }
    ]
    report = storylines.build_league_storylines(txs, profiles={}, season="2026")
    html = league_storylines_ui.storylines_panel_html(report, team_logo_html=_logo)
    assert "Unknown team" in html
    assert "Team 99" not in html
    assert "roster_id" not in html
    assert report["most_picks_acquired"] is None


def test_storyline_helpers_are_deterministic_and_fast():
    import time

    txs = _normalized(
        [
            _tx(transaction_id="t1", type="trade", adds={"p1": 2, "p2": 1}),
            _tx(
                transaction_id="w1",
                type="waiver",
                roster_ids=[1],
                adds={"p3": 1},
                settings={"waiver_bid": 11},
            ),
        ]
    )
    first = time.perf_counter()
    storylines.build_league_storylines(txs, profiles=PROFILES, season="2026")
    first_ms = (time.perf_counter() - first) * 1000
    second = time.perf_counter()
    storylines.build_league_storylines(txs, profiles=PROFILES, season="2026")
    second_ms = (time.perf_counter() - second) * 1000
    assert first_ms < 50
    assert second_ms < 50
    html = league_storylines_ui.storylines_panel_html(
        storylines.build_league_storylines(txs, profiles=PROFILES, season="2026"),
        team_logo_html=_logo,
        season="2026",
    )
    assert "dg-ls-grid" in html
    assert "dg-mg-bar" in html or "dg-mg-rank" in html
    assert "chart.js" not in html.lower()

