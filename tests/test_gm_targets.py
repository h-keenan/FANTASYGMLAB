"""Experimental GM Targets — preference CRUD and football non-interference contracts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from modules import decision_change_history as dch
from modules import gm_targets as gt
from modules import notification_center as nc
from modules import premium
from modules import recommendation_lifecycle as lifecycle
from modules import session_integrity


ROOT = Path(__file__).resolve().parents[1]


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


def test_kill_switch_defaults_on():
    assert gt.experiment_enabled(environ={}) is True
    assert gt.experiment_enabled(environ={gt.EXPERIMENT_ENV_KEY: "0"}) is False
    assert gt.experiment_enabled(environ={gt.EXPERIMENT_ENV_KEY: "1"}) is True


def test_free_can_persist_with_limited_cap():
    session = _free_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    assert gt.can_access_targets(session, environ=env) is True
    assert gt.can_show_discovery(session, environ=env) is False
    assert gt.should_sync_durable(session, environ=env) is True
    assert gt.max_targets_for_session(session) == gt.MAX_TARGETS_FREE


def test_premium_can_persist_when_experiment_on():
    session = _premium_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    assert gt.can_access_targets(session, environ=env) is True
    assert gt.should_sync_durable(session, environ=env) is True
    assert gt.max_targets_for_session(session) == gt.MAX_TARGETS_PREMIUM


def test_anonymous_cannot_access():
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    assert gt.can_access_targets({}, environ=env) is False
    assert gt.can_show_discovery({}, environ=env) is True


def test_add_target_idempotent_and_cached():
    session = _premium_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    writes: list[dict] = []

    def fake_upsert(config, token, table, payload, *, on_conflict):
        writes.append(payload)
        assert on_conflict == "user_id,league_id,player_id"
        assert table == gt.TARGETS_TABLE
        return True, ""

    with (
        patch.object(gt, "experiment_enabled", return_value=True),
        patch.object(gt.account_store, "upsert_row", side_effect=fake_upsert),
        patch.object(gt.account_store, "fetch_rows", return_value=([], "")),
        patch.object(gt.auth_supabase, "is_configured", return_value=True),
        patch.object(
            gt, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}
        ),
    ):
        first = gt.add_target(
            session, league_id="L1", player_id="6794", source_surface="pqv", environ=env
        )
        second = gt.add_target(
            session, league_id="L1", player_id="6794", environ=env
        )
    assert first["ok"] is True
    assert second["ok"] is True
    assert second["duplicate"] is True
    assert len(writes) == 1
    assert gt.is_targeted(session, league_id="L1", player_id="6794")


def test_remove_target_updates_cache_without_deleting_history():
    session = _premium_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    session[dch.DECISION_HISTORY_EVENTS_KEY] = [
        dch.DecisionChangeEvent(
            event_id="e1",
            recommendation_id="r1",
            league_id="L1",
            roster_id="1",
            timestamp=1.0,
            lifecycle_transition="appeared",
            reason="test",
            category="Trades",
            target_label="Josh Jacobs",
            player_id="6794",
            destination="trade_hub",
            previous_state={},
            current_state={},
            previous_priority=None,
            current_priority=1,
            current_confidence_band="medium",
            scoring_format="PPR",
            valuation_lens="dynasty",
            summary_headline="Recommendation appeared",
            summary_detail="Jacobs rose",
            why_label="",
        ).to_dict()
    ]
    session[dch.DECISION_HISTORY_LEAGUE_SCOPE_KEY] = "L1"
    gt._cache_targets(
        session,
        league_id="L1",
        targets=[
            gt.GmTarget(
                user_id="11111111-1111-1111-1111-111111111111",
                league_id="L1",
                player_id="6794",
                created_ts=1.0,
            )
        ],
    )

    with (
        patch.object(gt, "experiment_enabled", return_value=True),
        patch.object(gt.account_store, "delete_rows", return_value=(True, "")),
        patch.object(gt.auth_supabase, "is_configured", return_value=True),
        patch.object(
            gt, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}
        ),
    ):
        result = gt.remove_target(session, league_id="L1", player_id="6794", environ=env)

    assert result["ok"] is True
    assert not gt.is_targeted(session, league_id="L1", player_id="6794")
    assert len(dch.list_decision_events(session, league_id="L1")) == 1


def test_league_isolation_of_session_cache():
    session = _premium_session()
    gt._cache_targets(
        session,
        league_id="LA",
        targets=[
            gt.GmTarget(
                user_id="u", league_id="LA", player_id="1", created_ts=1.0
            )
        ],
    )
    assert gt.is_targeted(session, league_id="LA", player_id="1")
    assert not gt.is_targeted(session, league_id="LB", player_id="1")
    gt.clear_gm_targets_session(session)
    assert not gt.is_targeted(session, league_id="LA", player_id="1")


def test_account_switch_clears_gm_targets_session():
    session = _premium_session()
    gt._cache_targets(
        session,
        league_id="L1",
        targets=[
            gt.GmTarget(
                user_id="u", league_id="L1", player_id="9", created_ts=1.0
            )
        ],
    )
    session_integrity.clear_account_bound_transient_state(session)
    assert gt.SESSION_CACHE_IDS_KEY not in session


def test_cap_fifty_targets_per_league():
    session = _premium_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    filled = [
        gt.GmTarget(
            user_id="11111111-1111-1111-1111-111111111111",
            league_id="L1",
            player_id=str(i),
            created_ts=float(i),
        )
        for i in range(gt.MAX_TARGETS_PER_LEAGUE)
    ]
    gt._cache_targets(session, league_id="L1", targets=filled)
    with (
        patch.object(gt, "experiment_enabled", return_value=True),
        patch.object(gt.auth_supabase, "is_configured", return_value=True),
        patch.object(
            gt, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}
        ),
    ):
        result = gt.add_target(
            session, league_id="L1", player_id="new-player", environ=env
        )
    assert result["ok"] is False
    assert result["at_cap"] is True
    assert "50" in result["error"]


def test_missing_table_marks_unavailable_softly():
    session = _premium_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    with (
        patch.object(gt, "experiment_enabled", return_value=True),
        patch.object(
            gt.account_store,
            "fetch_rows",
            return_value=([], "relation \"gm_targets\" does not exist"),
        ),
        patch.object(gt.auth_supabase, "is_configured", return_value=True),
        patch.object(
            gt, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}
        ),
    ):
        rows = gt.fetch_targets_for_league(
            session, league_id="L1", environ=env, force=True
        )
    assert rows == ()
    assert session.get(gt.SESSION_UNAVAILABLE_KEY) is True
    assert gt.should_sync_durable(session, environ=env) is False


def test_ownership_and_rank_formatting():
    assert (
        gt.ownership_status("1", my_roster_player_ids=["1"], owner_by_player_id={})
        == "On your roster"
    )
    assert (
        gt.ownership_status(
            "2",
            my_roster_player_ids=["1"],
            owner_by_player_id={"2": {"owner_team_name": "Foxes"}},
        )
        == "Rostered by Foxes"
    )
    assert (
        gt.ownership_status("3", my_roster_player_ids=["1"], owner_by_player_id={})
        == "Free agent / waiver"
    )
    line = gt.format_rank_line(
        {"overall_rank": 14, "position_rank": 6, "position": "WR"},
        scoring_format="PPR",
    )
    assert line == "OVR #14 · WR #6 · PPR"


def test_no_synthetic_recommendation_without_canonical_source():
    action = gt.resolve_canonical_action({}, player_id="6794", league_id="L1")
    assert action["mode"] == "none"
    assert action["action"] == ""


def test_material_change_reuses_decision_events_only():
    session = {
        dch.DECISION_HISTORY_EVENTS_KEY: [
            dch.DecisionChangeEvent(
                event_id="e1",
                recommendation_id="r1",
                league_id="L1",
                roster_id="1",
                timestamp=1.0,
                lifecycle_transition="appeared",
                reason="test",
                category="Trades",
                target_label="Josh Jacobs",
                player_id="6794",
                destination="trade_hub",
                previous_state={},
                current_state={},
                previous_priority=None,
                current_priority=1,
                current_confidence_band="medium",
                scoring_format="PPR",
                valuation_lens="dynasty",
                summary_headline="Recommendation strengthened",
                summary_detail="Priority rose",
                why_label="",
            ).to_dict()
        ],
        dch.DECISION_HISTORY_LEAGUE_SCOPE_KEY: "L1",
    }
    change = gt.material_change_for_player(session, player_id="6794", league_id="L1")
    assert change["label"] == "Recommendation strengthened"
    assert gt.material_change_for_player(session, player_id="other", league_id="L1")[
        "label"
    ] == ""


def test_sort_presentation_contract():
    cards = [
        gt.EnrichedTargetCard(
            player_id="b",
            name="B",
            position="WR",
            team="X",
            image_player_id="b",
            rank_line="",
            ownership="",
            action="",
            action_summary="",
            action_destination="",
            material_label="",
            material_detail="",
            material_destination="",
            overall_rank=5,
            created_ts=10.0,
            has_action=False,
            has_material_change=False,
        ),
        gt.EnrichedTargetCard(
            player_id="a",
            name="A",
            position="RB",
            team="Y",
            image_player_id="a",
            rank_line="",
            ownership="",
            action="BUY",
            action_summary="",
            action_destination="trade_hub",
            material_label="",
            material_detail="",
            material_destination="",
            overall_rank=20,
            created_ts=1.0,
            has_action=True,
            has_material_change=False,
        ),
    ]
    ordered = gt.sort_enriched_targets(cards)
    assert ordered[0].player_id == "a"


def test_add_remove_does_not_invalidate_football_frame_keys():
    session = _premium_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    session["_prepared_valued_ranked_frame"] = {"sentinel": True}
    session[lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY] = {"r1": "sig"}
    with (
        patch.object(gt, "experiment_enabled", return_value=True),
        patch.object(gt.account_store, "upsert_row", return_value=(True, "")),
        patch.object(gt.account_store, "fetch_rows", return_value=([], "")),
        patch.object(gt.account_store, "delete_rows", return_value=(True, "")),
        patch.object(gt.auth_supabase, "is_configured", return_value=True),
        patch.object(
            gt, "_resolve_config", return_value={"enabled": True, "url": "x", "anon_key": "y"}
        ),
    ):
        gt.add_target(session, league_id="L1", player_id="1", environ=env)
        gt.remove_target(session, league_id="L1", player_id="1", environ=env)
    assert session["_prepared_valued_ranked_frame"] == {"sentinel": True}
    assert session[lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY] == {"r1": "sig"}


def test_recommendation_equivalence_enabled_disabled_and_targeted():
    """GM Targets must not alter inventory signatures or recommendation ids."""

    def _tile():
        return {
            "label": "Top Trade Opportunity",
            "value": "Josh Jacobs",
            "note": "You move from TE surplus.",
            "recommendation_id": "t1",
            "route_key": "trade_hub",
            "route_player_id": "6794",
            "recommendation_narrative": {
                "recommendation_id": "t1",
                "kind": "trade",
                "action": "Buy need-position upgrade",
                "target_label": "Josh Jacobs",
                "reason": "You move from TE surplus.",
                "confidence_label": "Medium",
                "is_active_recommendation": True,
            },
        }

    tiles = [_tile()]
    off_session: dict = {}
    on_session = _premium_session()
    targeted_session = _premium_session()
    gt._cache_targets(
        targeted_session,
        league_id="L1",
        targets=[
            gt.GmTarget(
                user_id="u", league_id="L1", player_id="6794", created_ts=1.0
            )
        ],
    )
    ten = _premium_session()
    gt._cache_targets(
        ten,
        league_id="L1",
        targets=[
            gt.GmTarget(user_id="u", league_id="L1", player_id=str(i), created_ts=1.0)
            for i in range(10)
        ],
    )

    nc.publish_activity_inventory(off_session, tiles, league_id="L1", context_fingerprint="fp")
    with patch.object(gt, "experiment_enabled", return_value=True):
        nc.publish_activity_inventory(
            on_session, tiles, league_id="L1", context_fingerprint="fp"
        )
        nc.publish_activity_inventory(
            targeted_session, tiles, league_id="L1", context_fingerprint="fp"
        )
        nc.publish_activity_inventory(
            ten, tiles, league_id="L1", context_fingerprint="fp"
        )

    def _sig(session):
        return session.get(lifecycle.LIFECYCLE_INVENTORY_SIGNATURES_KEY)

    def _ids(session):
        snap = session.get(nc.ACTIVITY_INBOX_SNAPSHOT_KEY) or {}
        return [r.get("recommendation_id") for r in snap.get("records") or []]

    assert _sig(off_session) == _sig(on_session) == _sig(targeted_session) == _sig(ten)
    assert _ids(off_session) == _ids(on_session) == _ids(targeted_session) == _ids(ten)


def test_migration_sql_rls_and_identity_contract():
    sql = (ROOT / "docs" / "supabase_gm_targets.sql").read_text(encoding="utf-8")
    assert "gm_targets" in sql
    assert "enable row level security" in sql
    assert "auth.uid() = user_id" in sql
    assert "primary key (user_id, league_id, player_id)" in sql
    assert "on delete cascade" in sql.casefold()
    assert "to anon" not in sql
    assert "for update" not in sql.casefold()


def test_ui_and_contract_docs_exist():
    ui = (ROOT / "modules" / "gm_targets_ui.py").read_text(encoding="utf-8")
    doc = (ROOT / "docs" / "experimental-gm-targets-contract.md").read_text(
        encoding="utf-8"
    )
    assert "Add to GM Targets" in ui or gt.ADD_ACTION_LABEL
    assert "data-gm-target=" in ui
    assert "data-gm-targets-discovery=" in ui
    assert "DYNASTYGM_EXPERIMENTAL_GM_TARGETS" in doc
    assert "50" in doc or "Premium **50**" in doc
    assert "Never modifies" in (ROOT / "modules" / "gm_targets.py").read_text(
        encoding="utf-8"
    )


def test_app_wires_pqv_and_destination_without_critical_path_fetch():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "gm_targets_ui.render_pqv_target_control" in app
    assert 'current_page == "gm_targets"' in app
    assert "gm_targets.clear_gm_targets_session" in app
    assert 'enabled_experimental_keys.append("gm_targets")' in app
    # Membership hydrate stays inside the PQV control / workspace, not shell bootstrap.
    assert "ensure_membership_cache" not in app.split("destination_visibility")[0]


def test_no_n_plus_one_fetch_helper_is_list_based():
    source = (ROOT / "modules" / "gm_targets.py").read_text(encoding="utf-8")
    assert "def fetch_targets_for_league" in source
    assert "def ensure_membership_cache" in source
    assert source.count("account_store.fetch_rows") <= 2


def test_uses_canonical_get_supabase_config_not_removed_api():
    source = (ROOT / "modules" / "gm_targets.py").read_text(encoding="utf-8")
    assert "auth_supabase.load_supabase_config" not in source
    assert "auth_supabase.get_supabase_config" in source
    assert not hasattr(gt.auth_supabase, "load_supabase_config")
    assert hasattr(gt.auth_supabase, "get_supabase_config")


def test_resolve_config_valid_explicit_and_loader():
    explicit = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
    assert gt._resolve_config(explicit) == explicit

    with patch.object(
        gt.auth_supabase,
        "get_supabase_config",
        return_value={"enabled": True, "url": "https://x.supabase.co", "anon_key": "k"},
    ) as loader:
        resolved = gt._resolve_config(None)
    loader.assert_called_once()
    assert resolved["enabled"] is True
    assert resolved["anon_key"] == "k"


def test_resolve_config_missing_and_malformed_fail_soft():
    with patch.object(
        gt.auth_supabase,
        "get_supabase_config",
        return_value={"enabled": False, "url": "", "anon_key": ""},
    ):
        missing = gt._resolve_config(None)
    assert gt.auth_supabase.is_configured(missing) is False

    with patch.object(
        gt.auth_supabase, "get_supabase_config", side_effect=RuntimeError("boom")
    ):
        broken = gt._resolve_config(None)
    assert broken == {}
    assert gt.auth_supabase.is_configured(broken) is False


def test_fetch_fail_soft_unauthenticated_and_missing_config():
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    # Unauthenticated
    assert gt.fetch_targets_for_league({}, league_id="L1", environ=env) == ()

    # Authenticated Free but config absent — must not AttributeError / raise
    session = _free_session()
    with patch.object(
        gt.auth_supabase,
        "get_supabase_config",
        return_value={"enabled": False, "url": "", "anon_key": ""},
    ):
        rows = gt.fetch_targets_for_league(session, league_id="L1", environ=env)
    assert rows == ()

    # Malformed loader exception
    with patch.object(
        gt.auth_supabase, "get_supabase_config", side_effect=KeyError("SUPABASE_URL")
    ):
        rows = gt.fetch_targets_for_league(session, league_id="L1", environ=env)
    assert rows == ()


def test_fetch_with_valid_config_scopes_league_and_user():
    session = _premium_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    captured = {}

    def fake_fetch(config, token, table, *, user_id, extra_query, timing_label):
        captured["config"] = config
        captured["token"] = token
        captured["user_id"] = user_id
        captured["extra_query"] = extra_query
        assert table == gt.TARGETS_TABLE
        return (
            [
                {
                    "user_id": "11111111-1111-1111-1111-111111111111",
                    "league_id": "L1",
                    "player_id": "6794",
                    "source_surface": "pqv",
                    "created_at": "2026-01-01T00:00:00Z",
                },
                {
                    "user_id": "11111111-1111-1111-1111-111111111111",
                    "league_id": "OTHER",
                    "player_id": "9999",
                    "source_surface": "pqv",
                    "created_at": "2026-01-01T00:00:00Z",
                },
            ],
            "",
        )

    with (
        patch.object(gt.account_store, "fetch_rows", side_effect=fake_fetch),
        patch.object(
            gt,
            "_resolve_config",
            return_value={"enabled": True, "url": "https://x.supabase.co", "anon_key": "anon"},
        ),
    ):
        rows = gt.fetch_targets_for_league(session, league_id="L1", environ=env, force=True)

    assert captured["token"] == "tok"
    assert captured["user_id"] == "11111111-1111-1111-1111-111111111111"
    assert "league_id=eq.L1" in captured["extra_query"]
    assert [t.player_id for t in rows] == ["6794"]
    assert all(t.league_id == "L1" for t in rows)


def test_free_and_premium_caps_unchanged_by_config_fix():
    free = _free_session()
    prem = _premium_session()
    assert gt.max_targets_for_session(free) == gt.MAX_TARGETS_FREE
    assert gt.max_targets_for_session(prem) == gt.MAX_TARGETS_PREMIUM
    # Config absence must not elevate Free → Premium.
    with patch.object(gt, "_resolve_config", return_value={}):
        assert gt.max_targets_for_session(free) == gt.MAX_TARGETS_FREE
        assert gt.can_access_targets(free, environ={gt.EXPERIMENT_ENV_KEY: "1"}) is True


def test_league_switch_clears_cache_no_stale_leakage():
    session = _premium_session()
    env = {gt.EXPERIMENT_ENV_KEY: "1"}
    gt._cache_targets(
        session,
        league_id="L1",
        targets=(
            gt.GmTarget(
                user_id="11111111-1111-1111-1111-111111111111",
                league_id="L1",
                player_id="6794",
            ),
        ),
    )
    assert "6794" in gt.cached_target_ids(session, league_id="L1")
    gt.clear_gm_targets_session(session)
    assert gt.cached_target_ids(session, league_id="L1") == frozenset()
    assert gt.cached_target_ids(session, league_id="L2") == frozenset()
    # After switch, fetch for L2 must not resurrect L1 ids without a new list call.
    with (
        patch.object(gt.account_store, "fetch_rows", return_value=([], "")),
        patch.object(
            gt,
            "_resolve_config",
            return_value={"enabled": True, "url": "https://x.supabase.co", "anon_key": "anon"},
        ),
    ):
        rows = gt.fetch_targets_for_league(session, league_id="L2", environ=env, force=True)
    assert rows == ()
    assert gt.cached_target_ids(session, league_id="L2") == frozenset()
    assert "6794" not in gt.cached_target_ids(session, league_id="L1")


def test_no_stale_auth_supabase_loaders_in_repo():
    """Wider drift check — no production call sites for the removed loader."""

    offenders = []
    needle = "auth_supabase.load_supabase_config"
    for path in (*ROOT.glob("*.py"), *(ROOT / "modules").rglob("*.py"), *(ROOT / "scripts").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if needle in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
