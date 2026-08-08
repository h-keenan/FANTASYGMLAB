from pathlib import Path

from modules import runtime_trace
from scripts.measure_local_streamlit_e2e import _summarize_milestones


APP_PATH = Path("app.py")


def test_startup_milestones_are_safe_structural_labels():
    expected = {
        "auth_storage_bridge_complete",
        "profile_lookup_complete",
        "entitlement_lookup_complete",
        "league_restore_complete",
        "route_restore_complete",
    }

    assert expected <= runtime_trace.SAFE_MILESTONES
    assert all("user" not in label and "token" not in label for label in expected)


def test_startup_milestones_follow_the_production_execution_order():
    source = APP_PATH.read_text(encoding="utf-8")
    labels = (
        "auth_storage_bridge_complete",
        "profile_lookup_complete",
        "entitlement_lookup_complete",
        "authentication_complete",
        "league_restore_complete",
        "session_initialization_complete",
        "public_player_load_complete",
        "league_data_complete",
        "route_restore_complete",
        "page_calculation_complete",
    )

    offsets = [source.index(f'runtime_trace.mark("{label}")') for label in labels]

    assert offsets == sorted(offsets)
    deferred = source.index('runtime_trace.mark("public_player_load_deferred")')
    assert source.index('runtime_trace.mark("session_initialization_complete")') < deferred


def test_auth_and_league_restore_continue_same_run_without_forced_reruns():
    """Returning auth must settle profile/league in the restore run (no cascade)."""

    source = APP_PATH.read_text(encoding="utf-8")
    main = source.index("def main():")
    auth_restore = source.index('if auth_restore.get("restored"):', main)
    profile = source.index('runtime_trace.mark("profile_lookup_complete")', auth_restore)
    league_restore = source.index("_maybe_auto_resume_supabase_league()", auth_restore)
    session_ready = source.index(
        'runtime_trace.mark("session_initialization_complete")',
        auth_restore,
    )

    assert auth_restore < profile < league_restore < session_ready
    assert "st.rerun()" not in source[auth_restore:profile]
    assert "st.rerun()" not in source[league_restore:session_ready]


def test_startup_shell_precedes_player_loading_and_authentication_without_css_override():
    app_source = APP_PATH.read_text(encoding="utf-8")
    css_source = Path("modules/app_styles.py").read_text(encoding="utf-8")
    polish_source = Path("modules/ux_polish_styles.py").read_text(encoding="utf-8")

    shell = app_source.index("StartupCoordinator.begin(st.session_state)")
    auth = app_source.index("auth_restore = account_ui.render_durable_auth_bridge")
    player_load = app_source.index("normalize_player_ids(ensure_players())")
    session_ready = app_source.index('runtime_trace.mark("session_initialization_complete")')

    assert shell < auth < session_ready < player_load
    assert 'st.spinner("Loading player data...")' not in app_source
    assert "stSpinner" not in css_source
    assert "stSpinner" not in polish_source
    assert 'data-fgl-shell-ready="1"' in app_source
    assert 'data-fgl-dashboard-useful="1"' in app_source
    assert 'data-fgl-dashboard-complete="1"' in app_source


def test_startup_milestone_summary_retains_only_shared_structural_labels():
    samples = [
        {"milestones": {"public_player_load_complete": 20, "route_restore_complete": 90}},
        {
            "milestones": {
                "public_player_load_complete": 30,
                "route_restore_complete": 100,
                "one_sample_only": 1,
            }
        },
    ]

    summary = _summarize_milestones(samples)

    assert set(summary) == {"public_player_load_complete", "route_restore_complete"}
    assert summary["public_player_load_complete"]["median"] == 25.0
