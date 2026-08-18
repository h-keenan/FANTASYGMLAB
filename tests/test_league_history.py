"""League History v1 — normalize Sleeper transactions into a readable timeline."""

from __future__ import annotations

from pathlib import Path

from modules import league_history as history
from modules import league_history_ui
from modules.app_styles import APP_CSS
from modules.league_history_styles import LEAGUE_HISTORY_CSS
from modules.ui_architecture import PLATFORM_DESTINATIONS


ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    "1": {
        "team_name": "War Room",
        "username": "alpha",
        "owner_name": "Alpha Manager",
        "avatar_url": "https://sleepercdn.com/avatars/aaa",
    },
    "2": {
        "team_name": "Lakefront",
        "username": "beta",
        "owner_name": "Beta Manager",
        "avatar_url": "",
    },
}

PLAYERS = {
    "p1": {"name": "Ja'Marr Chase", "position": "WR", "team": "CIN"},
    "p2": {"name": "Breece Hall", "position": "RB", "team": "NYJ"},
    "p3": {"name": "Trey McBride", "position": "TE", "team": "ARI"},
}


def _normalize(raw, *, week=4, season="2026", league_id="L-now"):
    return history.normalize_transaction(
        raw,
        league_id=league_id,
        season=season,
        week=week,
        profiles=PROFILES,
        player_lookup=PLAYERS,
    )


def _logo(url, name, css_class="dg-lh-logo"):
    return f"<div class='{css_class}'>{name[:2]}</div>"


def test_trade_players_only_preserves_receive_direction():
    tx = _normalize(
        {
            "transaction_id": "t-players",
            "type": "trade",
            "status": "complete",
            "status_updated": 1_700_000_000_000,
            "roster_ids": [1, 2],
            "adds": {"p1": 2, "p2": 1},
            "drops": {"p2": 2, "p1": 1},
            "draft_picks": [],
        }
    )
    by_team = {side["roster_id"]: side for side in tx["sides"]}
    assert [asset["name"] for asset in by_team["2"]["receives"]] == ["Ja'Marr Chase"]
    assert [asset["name"] for asset in by_team["1"]["receives"]] == ["Breece Hall"]
    html = league_history_ui.history_item_html(tx, team_logo_html=_logo)
    assert "Got" in html
    assert "Chase" in html
    assert "winner" not in html.casefold()
    assert "fleeced" not in html.casefold()
    assert "adds" not in html


def test_trade_players_and_picks_and_multi_asset():
    tx = _normalize(
        {
            "transaction_id": "t-multi",
            "type": "trade",
            "status": "complete",
            "roster_ids": [1, 2],
            "adds": {"p1": 1, "p3": 1, "p2": 2},
            "drops": {},
            "draft_picks": [
                {"season": "2027", "round": 1, "owner_id": 2, "previous_owner_id": 1},
                {"season": "2028", "round": 3, "owner_id": 1, "previous_owner_id": 2},
            ],
        }
    )
    by_team = {side["roster_id"]: side for side in tx["sides"]}
    names_1 = [asset["label"] for asset in by_team["1"]["receives"]]
    names_2 = [asset["label"] for asset in by_team["2"]["receives"]]
    assert "Ja'Marr Chase" in names_1 and "Trey McBride" in names_1
    assert "2028 3rd" in names_1
    assert "Breece Hall" in names_2 and "2027 1st" in names_2
    html = league_history_ui.history_item_html(tx, team_logo_html=_logo)
    assert "2027 1st" in html


def test_waiver_with_and_without_faab():
    with_faab = _normalize(
        {
            "transaction_id": "w-faab",
            "type": "waiver",
            "status": "complete",
            "roster_ids": [1],
            "adds": {"p3": 1},
            "drops": {"p2": 1},
            "settings": {"waiver_bid": 17},
        }
    )
    html = league_history_ui.history_item_html(with_faab, team_logo_html=_logo)
    assert "Waiver" in html and "FAAB $17" in html and "Dropped" in html
    no_faab = _normalize(
        {
            "transaction_id": "w-none",
            "type": "waiver",
            "status": "complete",
            "roster_ids": [1],
            "adds": {"p1": 1},
        }
    )
    html_none = league_history_ui.history_item_html(no_faab, team_logo_html=_logo)
    assert "FAAB" not in html_none
    assert "waiver_bid" not in html_none


def test_free_agent_add_and_add_drop():
    html = league_history_ui.history_item_html(
        _normalize(
            {
                "transaction_id": "fa-1",
                "type": "free_agent",
                "status": "complete",
                "roster_ids": [2],
                "adds": {"p2": 2},
            }
        ),
        team_logo_html=_logo,
    )
    assert "Free agent" in html and "Added" in html and "Dropped" not in html
    html_churn = league_history_ui.history_item_html(
        _normalize(
            {
                "transaction_id": "fa-drop",
                "type": "free_agent",
                "status": "complete",
                "roster_ids": [2],
                "adds": {"p1": 2},
                "drops": {"p2": 2},
            }
        ),
        team_logo_html=_logo,
    )
    assert "Dropped" in html_churn


def test_prior_season_traversal_and_missing_previous():
    leagues = {
        "L-26": {
            "season": "2026",
            "previous_league_id": "L-25",
            "status": "in_season",
            "settings": {"leg": 8},
        },
        "L-25": {
            "season": "2025",
            "previous_league_id": "L-24",
            "status": "complete",
            "settings": {"last_scored_leg": 17, "playoff_week_start": 15},
        },
        "L-24": {
            "season": "2024",
            "previous_league_id": "",
            "status": "complete",
            "settings": {"last_scored_leg": 17},
        },
    }
    chain = history.walk_season_chain("L-26", leagues.get)
    assert [item["season"] for item in chain] == ["2026", "2025", "2024"]
    orphan = history.walk_season_chain(
        "solo",
        lambda _lid: {"season": "2026", "previous_league_id": "", "settings": {"leg": 3}},
    )
    assert len(orphan) == 1
    cycled = history.walk_season_chain(
        "loop",
        lambda lid: {"season": "2026", "previous_league_id": lid, "settings": {"leg": 1}},
    )
    assert len(cycled) == 1


def test_local_filter_does_not_need_refetch():
    calls = {"n": 0}

    def fetch_league(_league_id):
        return {"season": "2026", "settings": {"leg": 2}}

    def fetch_transactions(_league_id, week):
        calls["n"] += 1
        if week != 1:
            return []
        return [
            {
                "transaction_id": "t1",
                "type": "trade",
                "status": "complete",
                "adds": {"p1": 1, "p2": 2},
                "roster_ids": [1, 2],
                "draft_picks": [
                    {"season": "2027", "round": 1, "owner_id": 1, "previous_owner_id": 2}
                ],
            },
            {
                "transaction_id": "w1",
                "type": "waiver",
                "status": "complete",
                "adds": {"p3": 1},
                "settings": {"waiver_bid": 5},
            },
            {
                "transaction_id": "f1",
                "type": "free_agent",
                "status": "complete",
                "adds": {"p2": 2},
            },
        ]

    payload = history.collect_season_transactions(
        "L-now",
        fetch_league=fetch_league,
        fetch_transactions=fetch_transactions,
    )
    first_calls = calls["n"]
    normalized = history.normalize_season_payload(
        payload, profiles=PROFILES, player_lookup=PLAYERS
    )
    assert [row["type"] for row in history.filter_history(normalized, history.FILTER_TRADES)] == [
        "trade"
    ]
    assert [row["type"] for row in history.filter_history(normalized, history.FILTER_WAIVERS)] == [
        "waiver"
    ]
    assert [
        row["type"] for row in history.filter_history(normalized, history.FILTER_FREE_AGENTS)
    ] == ["free_agent"]
    assert all(row.get("draft_picks") for row in history.filter_history(normalized, history.FILTER_PICKS))
    assert calls["n"] == first_calls == 2


def test_cache_isolation_by_league_and_season():
    def fetch_league(league_id):
        return {"season": "2026" if league_id == "A" else "2025", "settings": {"leg": 1}}

    def fetch_transactions(league_id, week):
        return [
            {
                "transaction_id": f"{league_id}-{week}",
                "type": "free_agent",
                "status": "complete",
                "adds": {"p1": 1},
            }
        ]

    payload_a = history.collect_season_transactions(
        "A", fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )
    payload_b = history.collect_season_transactions(
        "B", fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )
    assert payload_a["season"] == "2026"
    assert payload_b["season"] == "2025"
    assert payload_a["transactions"][0]["transaction_id"] == "A-1"
    assert payload_b["transactions"][0]["transaction_id"] == "B-1"


def test_empty_unknown_malformed_and_no_history():
    assert _normalize({"type": "trade", "status": "complete"}) is None
    unknown = _normalize(
        {
            "transaction_id": "unk",
            "type": "trade",
            "status": "complete",
            "adds": {"ghost": 9, "p1": 1},
            "roster_ids": [9, 1],
        }
    )
    names = [asset["name"] for asset in unknown["adds"]]
    assert "Unavailable player" in names
    html = league_history_ui.history_item_html(unknown, team_logo_html=_logo)
    assert "Unknown team" in html
    assert "ghost" not in html
    malformed = _normalize(
        {
            "transaction_id": "pick-bad",
            "type": "trade",
            "status": "complete",
            "roster_ids": [1, 2],
            "draft_picks": [{"owner_id": 1, "previous_owner_id": 2}],
        }
    )
    assert malformed["draft_picks"][0]["label"] == "Draft pick"
    html_pick = league_history_ui.history_item_html(malformed, team_logo_html=_logo)
    assert "previous_owner_id" not in html_pick
    empty_html = league_history_ui.history_feed_html(
        [],
        team_logo_html=_logo,
        empty_note=league_history_ui.empty_filter_note(history.FILTER_ALL),
    )
    assert "No completed transactions yet" in empty_html


def test_long_names_and_mobile_css_contracts():
    tx = _normalize(
        {
            "transaction_id": "long",
            "type": "trade",
            "status": "complete",
            "adds": {"p1": 1},
            "roster_ids": [1, 2],
            "draft_picks": [{"season": "2027", "round": 1, "owner_id": 2, "previous_owner_id": 1}],
        }
    )
    tx["sides"][0]["team_name"] = "Very Long Dynasty Franchise Name That Should Wrap"
    html = league_history_ui.history_item_html(tx, team_logo_html=_logo)
    assert "Very Long Dynasty Franchise Name That Should Wrap" in html
    assert "@media (max-width:430px)" in LEAGUE_HISTORY_CSS
    assert "max-width:min(76rem,100%)" in LEAGUE_HISTORY_CSS.replace(" ", "")
    assert LEAGUE_HISTORY_CSS not in APP_CSS


def test_history_lives_on_league_memory_not_overview():
    keys = {page.key for page in PLATFORM_DESTINATIONS}
    assert "history" not in keys
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    recaps_ui = (ROOT / "modules" / "league_recaps_ui.py").read_text(encoding="utf-8")
    assert "league_history_ui.render_league_history_section(" not in app_source
    assert "league_history_ui.render_league_history_section(" in recaps_ui
    rankings = app_source.split('if current_page in {"rankings"', 1)[1].split(
        "# LEAGUE RECAPS", 1
    )[0]
    assert "cached_season_history_payload(" not in rankings
    ui_source = (ROOT / "modules" / "league_history_ui.py").read_text(encoding="utf-8")
    assert "st.rerun" not in ui_source
    assert "winner" not in ui_source.casefold()
    domain = (ROOT / "modules" / "league_history.py").read_text(encoding="utf-8")
    assert "get_transactions(" not in domain
    context = app_source.split("def get_shared_league_context(", 1)[1].split("\n    def ", 1)[0]
    assert "cached_season_history_payload" not in context


def test_first_load_fetch_count_vs_payload_reuse():
    calls = {"n": 0}

    def fetch_league(_league_id):
        return {"season": "2026", "status": "in_season", "settings": {"leg": 3}}

    def fetch_transactions(_league_id, week):
        calls["n"] += 1
        return []

    first = history.collect_season_transactions(
        "L", fetch_league=fetch_league, fetch_transactions=fetch_transactions
    )
    first_n = calls["n"]
    assert first_n == 3
    history.filter_history(
        history.normalize_season_payload(first, profiles=PROFILES, player_lookup=PLAYERS),
        history.FILTER_TRADES,
    )
    assert calls["n"] == first_n

