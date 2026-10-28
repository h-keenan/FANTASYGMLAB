"""Audit C6: ONE server-side league-format -> lens decision, used everywhere."""

from unittest.mock import Mock, patch

import pandas as pd

from modules import league_value_settings, push_triggers


def test_default_lens_for_league_is_the_one_decision():
    f = league_value_settings.default_lens_for_league
    assert f({"settings": {"type": 0}}) == "Non-Dynasty"  # redraft
    assert f({"settings": {"type": 1}}) == "Dynasty"  # keeper shares dynasty horizon math
    assert f({"settings": {"type": 2}}) == "Dynasty"
    assert f({"settings": {}}) == "Dynasty"  # undetectable -> default, never guessed
    assert f(None) == "Dynasty" and f({}) == "Dynasty"
    # Every lens it can return is a real valuation lens.
    for league in ({"settings": {"type": t}} for t in (0, 1, 2)):
        assert f(league) in league_value_settings.VALUATION_LENS_TO_SCORE_FIELD


def test_league_endpoint_returns_default_lens():
    from services import mobile_api_service

    league = {"league_id": "L1", "settings": {"type": 0}}
    with patch("services.mobile_api_service.sleeper.get_league", return_value=league):
        body = mobile_api_service.get_league(league_id="L1", _user={"id": "u"})
    assert body["default_lens"] == "Non-Dynasty"


def test_push_sweep_values_each_league_on_its_own_lens():
    lens_calls: list[str] = []

    def fake_load(lens, settings):
        lens_calls.append(lens)
        return pd.DataFrame([{"player_id": "p1", "position": "RB", "value_score": 1}]), "value_score"

    leagues = [
        {"league_id": "redraft-1", "name": "R", "settings": {"type": 0}},
        {"league_id": "dynasty-1", "name": "D", "settings": {"type": 2}},
    ]
    seen: dict[str, str] = {}

    def fake_briefing(**kwargs):
        seen[kwargs["league_id"]] = kwargs["score_field"]
        return []

    config = Mock(configured=True)
    with patch("modules.push_triggers.load_push_trigger_config", return_value=config), patch(
        "modules.push_triggers.load_weekly_push_cap", return_value=10
    ), patch("modules.push_triggers.fetch_push_recipients", return_value={"u1": ["tok"]}), patch(
        "modules.push_triggers.fetch_sleeper_usernames", return_value={"u1": "gm"}
    ), patch("modules.push_triggers.fetch_push_preferences", return_value={}), patch(
        "modules.push_triggers.fetch_push_timezones", return_value={}
    ), patch("modules.push_triggers.fetch_gm_stance_leagues", return_value={}), patch(
        "modules.push_triggers.fetch_gm_targets_untouchable_ids", return_value={}
    ), patch("modules.push_triggers.load_valued_players", side_effect=fake_load), patch(
        "modules.sleeper_leagues.resolve_sleeper_user_id", return_value="su1"
    ), patch("modules.sleeper_leagues.get_user_leagues", return_value=leagues), patch(
        "modules.sleeper.get_league", side_effect=lambda lid: next(l for l in leagues if l["league_id"] == lid)
    ), patch("modules.sleeper.get_rosters", return_value=[]), patch(
        "modules.push_triggers.league_briefing_push_items", side_effect=fake_briefing
    ), patch("modules.push_triggers.recap_push_item", return_value=None):
        push_triggers.run_push_trigger_sweep(environ={})

    assert sorted(lens_calls) == ["Dynasty", "Non-Dynasty"]  # one load per lens, cached
    assert seen == {"redraft-1": "value_score", "dynasty-1": "value_score"}


def test_trade_outcome_sweep_without_a_stored_lens_uses_the_leagues_own_lens():
    from modules import trade_outcome_results as tor

    def row(summary):
        return {
            "id": "o1", "user_id": "u1", "league_id": "league-r", "outcome_recorded_at": "2020-01-01T00:00:00+00:00",
            "trade_summary": {
                "send": [{"name": "A", "position": "RB", "player_id": "1", "value_score": 1000.0}],
                "receive": [{"name": "B", "position": "WR", "player_id": "2", "value_score": 1000.0}],
                **summary,
            },
        }

    response = Mock(status_code=200)
    response.json.return_value = [row({})]  # no stored valuation_lens
    valued_df = pd.DataFrame({"player_id": ["1", "2"], "value_score": [900.0, 1400.0]})
    with patch("requests.get", return_value=response), patch("requests.patch"), patch(
        "modules.sleeper.get_season_player_stats", return_value={}
    ), patch("modules.sleeper.get_league", return_value={"settings": {"type": 0}}), patch.object(
        tor, "load_valued_players_for_result", return_value=(valued_df, "value_score")
    ) as mock_load:
        tor.run_trade_outcome_result_sweep(
            environ={"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "srk"}
        )
    assert mock_load.call_args[0][0] == "Non-Dynasty"
