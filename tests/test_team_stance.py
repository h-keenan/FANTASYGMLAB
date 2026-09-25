"""Team Situation (Decision Memory v1 gap, #232) — stance CRUD + rationale framing.

Covers modules.team_stance (durable per-user, per-league stance storage) and
the additive rationale-framing layer in modules.trade_ideas. Confirms the
new feature never touches value_score/scoring, and that
modules/decision_memory.py (an unrelated recommendation-change-history log)
is untouched by this feature.
"""

from __future__ import annotations

from unittest.mock import patch

from modules import premium
from modules import team_stance as ts
from modules import trade_ideas


def _premium_session(**extra) -> dict:
    session = {
        "auth_session": {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "access_token": "tok",
        },
        "auth_user": {"id": "11111111-1111-1111-1111-111111111111"},
        "account_profile": {"entitlement": premium.PREMIUM},
    }
    session.update(extra)
    return session


def _free_session() -> dict:
    return {
        "auth_session": {
            "user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "access_token": "tok",
        },
        "auth_user": {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
        "account_profile": {"entitlement": premium.FREE},
    }


# --- normalize / labels -----------------------------------------------------


def test_normalize_stance_accepts_only_the_fixed_set():
    assert ts.normalize_stance("rebuilding") == ts.STANCE_REBUILDING
    assert ts.normalize_stance("Competing") == ts.STANCE_COMPETING
    assert ts.normalize_stance(" Balanced ") == ts.STANCE_BALANCED
    assert ts.normalize_stance("tanking") == ""
    assert ts.normalize_stance(None) == ""
    assert ts.normalize_stance("") == ""


def test_stance_options_is_exactly_three_fixed_categories():
    # Do not invent more categories without a reason (explicit product scope).
    assert ts.STANCE_OPTIONS == ("rebuilding", "competing", "balanced")
    assert set(ts.STANCE_LABELS) == set(ts.STANCE_OPTIONS)


# --- access control / kill switch ------------------------------------------


def test_kill_switch_defaults_on():
    assert ts.experiment_enabled(environ={}) is True
    assert ts.experiment_enabled(environ={ts.EXPERIMENT_ENV_KEY: "0"}) is False
    assert ts.experiment_enabled(environ={ts.EXPERIMENT_ENV_KEY: "1"}) is True


def test_anonymous_cannot_access():
    env = {ts.EXPERIMENT_ENV_KEY: "1"}
    assert ts.can_access_stance({}, environ=env) is False


def test_free_and_premium_both_have_access_no_premium_gate():
    # Unlike Decision Memory's durable history, a manual stance declaration
    # is not a Premium-only retention mechanic.
    env = {ts.EXPERIMENT_ENV_KEY: "1"}
    assert ts.can_access_stance(_free_session(), environ=env) is True
    assert ts.can_access_stance(_premium_session(), environ=env) is True


# --- set_stance / fetch_stance_for_league -----------------------------------


def test_set_stance_rejects_values_outside_the_fixed_set():
    session = _premium_session()
    env = {ts.EXPERIMENT_ENV_KEY: "1"}
    with (
        patch.object(ts.auth_supabase, "is_configured", return_value=True),
    ):
        result = ts.set_stance(session, league_id="L1", stance="tanking", environ=env)
    assert result["ok"] is False
    assert "Rebuilding" in result["error"]


def test_set_stance_upserts_on_user_league_conflict_and_caches():
    session = _premium_session()
    env = {ts.EXPERIMENT_ENV_KEY: "1"}
    writes: list[dict] = []

    def fake_upsert(config, token, table, payload, *, on_conflict):
        writes.append(payload)
        assert table == ts.STANCE_TABLE
        assert on_conflict == "user_id,league_id"
        return True, ""

    with (
        patch.object(ts.account_store, "upsert_row", side_effect=fake_upsert),
        patch.object(ts.auth_supabase, "is_configured", return_value=True),
    ):
        result = ts.set_stance(session, league_id="L1", stance="rebuilding", environ=env)

    assert result["ok"] is True
    assert len(writes) == 1
    assert writes[0]["stance"] == "rebuilding"
    assert writes[0]["league_id"] == "L1"
    # Cache-only read afterward should not need another network call.
    assert ts.cached_stance(session, league_id="L1") == "rebuilding"


def test_fetch_stance_for_league_fails_soft_on_missing_table():
    session = _premium_session()
    env = {ts.EXPERIMENT_ENV_KEY: "1"}
    with (
        patch.object(
            ts.account_store,
            "fetch_rows",
            return_value=([], "Could not find the table 'public.team_stance' in the schema cache"),
        ),
        patch.object(ts.auth_supabase, "is_configured", return_value=True),
    ):
        stance = ts.fetch_stance_for_league(session, league_id="L1")
    assert stance == ""
    assert session.get(ts.SESSION_UNAVAILABLE_KEY) is True


def test_fetch_stance_for_league_returns_stored_value():
    session = _premium_session()
    env = {ts.EXPERIMENT_ENV_KEY: "1"}
    with (
        patch.object(ts.account_store, "fetch_rows", return_value=([{"stance": "competing"}], "")),
        patch.object(ts.auth_supabase, "is_configured", return_value=True),
    ):
        stance = ts.fetch_stance_for_league(session, league_id="L1")
    assert stance == "competing"


def test_clear_team_stance_session_drops_cache_not_durable_rows():
    session = _premium_session()
    session[ts.SESSION_CACHE_STANCE_KEY] = "rebuilding"
    session[ts.SESSION_CACHE_LEAGUE_KEY] = "L1"
    session[ts.SESSION_HYDRATED_KEY] = "L1"
    ts.clear_team_stance_session(session)
    assert ts.SESSION_CACHE_STANCE_KEY not in session
    assert ts.cached_stance(session, league_id="L1") == ""


# --- rationale framing (modules.trade_ideas) --------------------------------


def test_team_stance_framing_clause_is_empty_for_no_stance():
    assert trade_ideas.team_stance_framing_clause("") == ""
    assert trade_ideas.team_stance_framing_clause("not-a-real-stance") == ""


def test_team_stance_framing_clause_per_stance():
    rebuild_clause = trade_ideas.team_stance_framing_clause("rebuilding")
    compete_clause = trade_ideas.team_stance_framing_clause("competing")
    balanced_clause = trade_ideas.team_stance_framing_clause("balanced")
    assert "rebuild" in rebuild_clause.casefold()
    assert "win-now" in compete_clause.casefold() or "immediate" in compete_clause.casefold()
    assert "balanced" in balanced_clause.casefold()
    assert len({rebuild_clause, compete_clause, balanced_clause}) == 3


def test_apply_team_stance_framing_is_noop_for_unset_stance():
    ideas = [{"rationale": "Solid value swap.", "value_score": 1234}]
    result = trade_ideas.apply_team_stance_framing(ideas, "")
    assert result is ideas
    assert result[0]["rationale"] == "Solid value swap."


def test_apply_team_stance_framing_appends_clause_and_preserves_everything_else():
    idea = {
        "rationale": "Solid value swap.",
        "value_score": 1234,
        "send_assets": [{"player_id": "1"}],
        "receive_assets": [{"player_id": "2"}],
        "priority": 42,
    }
    before_snapshot = {
        "value_score": idea["value_score"],
        "send_assets": idea["send_assets"],
        "receive_assets": idea["receive_assets"],
        "priority": idea["priority"],
    }
    result = trade_ideas.apply_team_stance_framing([idea], "rebuilding")

    # Additive only: rationale gained a clause, nothing numeric moved.
    assert result[0]["rationale"].startswith("Solid value swap.")
    assert "rebuild" in result[0]["rationale"].casefold()
    assert result[0]["team_stance_applied"] == "rebuilding"
    for key, value in before_snapshot.items():
        assert result[0][key] == value

    # Original dict passed in must not be mutated in place (safe to reuse
    # cached idea lists across different users/stances).
    assert idea["rationale"] == "Solid value swap."
    assert "team_stance_applied" not in idea


def test_apply_team_stance_framing_handles_empty_rationale():
    idea = {"rationale": ""}
    result = trade_ideas.apply_team_stance_framing([idea], "competing")
    assert result[0]["rationale"] == trade_ideas.team_stance_framing_clause("competing")


def test_apply_team_stance_framing_never_touches_value_score_field_name():
    # Explicit regression guard for the "presentation only" contract: the
    # framing function's own output must never introduce a value_score key
    # where one didn't already exist, and must never change one that did.
    idea = {"rationale": "x", "value_score": 999}
    result = trade_ideas.apply_team_stance_framing([idea], "balanced")
    assert result[0]["value_score"] == 999
    idea_no_score = {"rationale": "y"}
    result2 = trade_ideas.apply_team_stance_framing([idea_no_score], "balanced")
    assert "value_score" not in result2[0]


# --- name-collision guard: modules.decision_memory is unrelated -------------


def test_decision_memory_module_is_unrelated_and_untouched():
    from modules import decision_memory

    # Decision Memory is a recommendation-change-history log keyed on
    # events/baselines tables — it has no concept of a user-declared stance
    # and none of this feature's names should appear on it.
    assert not hasattr(decision_memory, "STANCE_OPTIONS")
    assert not hasattr(decision_memory, "set_stance")
    assert decision_memory.EVENTS_TABLE != ts.STANCE_TABLE
    assert decision_memory.BASELINES_TABLE != ts.STANCE_TABLE
