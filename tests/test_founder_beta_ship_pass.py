"""Founder Beta ship-pass regressions: portraits, league switch, startup, entitlement."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from modules import auth_restore_lifecycle
from modules import auth_supabase
from modules import compact_fantasy_assets as compact
from modules import game_plan_package
from modules import premium
from modules import session_integrity
from modules.game_plan_package import GAME_PLAN_CONTEXT_FLAGS
from modules.player_profile_ui import player_headshot_preset


ROOT = Path(__file__).resolve().parents[1]


class _State(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _seed_league(state: dict, league_id: str, *, extra: dict | None = None) -> None:
    state.update(
        {
            "selected_league_id": league_id,
            "selected_league_name": f"League {league_id[-1].upper()}",
            "username": "gm_user",
            "active_league_context": {
                "selected_league_id": league_id,
                "selected_league_name": f"League {league_id[-1].upper()}",
                "username": "gm_user",
                "my_roster_id": 1 if league_id.endswith("a") else 2,
            },
            "_effective_entitlement": "premium",
            "account_profile": {"entitlement": "premium", "user_id": "user-1"},
            "player_quick_view_player_id": "4046",
            "trade_hub_player_id": "4046",
            f"trade_hub_focus_player_id_{league_id}": "4046",
            f"trade_hub_mode_{league_id}": "find",
            "canonical_recommendation_narrative": {
                "recommendation_id": "rec-1",
                "league_id": league_id,
            },
            "trade_send_assets": [{"player_id": "4046"}],
            "_game_plan_package_bundle": {
                "briefing": {"league_id": league_id, "items": []},
                "league_id": league_id,
            },
            "_game_plan_package_signature": f"sig-{league_id}",
            "role_map": {"4046": "hold"},
        }
    )
    if extra:
        state.update(extra)


def test_session_key_lifetimes_keep_entitlement_account_owned():
    assert session_integrity.SESSION_KEY_LIFETIMES["_effective_entitlement"] == "ACCOUNT"
    assert session_integrity.SESSION_KEY_LIFETIMES["selected_league_id"] == "LEAGUE"
    assert session_integrity.SESSION_KEY_LIFETIMES["my_roster_id"] == "ROSTER"
    assert session_integrity.SESSION_KEY_LIFETIMES["players"] == "GLOBAL"
    assert session_integrity.SESSION_KEY_LIFETIMES["_game_plan_package_bundle"] == "LEAGUE"
    assert session_integrity.SESSION_KEY_LIFETIMES["_signal_intelligence_timeline"] == "LEAGUE"
    assert session_integrity.SESSION_KEY_LIFETIMES["_news_intelligence_timeline_events"] == "LEAGUE"


def test_rapid_switch_rejects_stale_game_plan_package():
    state = {
        "selected_league_id": "league-b",
        game_plan_package.PACKAGE_SIG_KEY: "same-sig",
        game_plan_package.PACKAGE_KEY: {
            "signature": "same-sig",
            "built_at": 9_999_999_999,
            "briefing": {"league_id": "league-a", "items": [{"headline": "A"}]},
        },
    }
    cached, hit = game_plan_package.lookup_package(
        state, signature="same-sig", expected_league_id="league-b"
    )
    assert hit is False
    assert cached is None
    assert state.get(game_plan_package.LAST_MISS_REASON_KEY) == "league_mismatch"
