"""What Changed mobile hierarchy + #294 refresh scheduling contracts."""

from __future__ import annotations

from pathlib import Path

from modules import decision_change_history as history
from modules import decision_change_history_ui as ui
from modules.app_styles import APP_CSS
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from tests.test_league_intelligence import NOW


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UI_SRC = (ROOT / "modules" / "decision_change_history_ui.py").read_text(encoding="utf-8")


def _event(**overrides) -> history.DecisionChangeEvent:
    payload = dict(
        event_id="e-resolved-1",
        recommendation_id="r1",
        league_id="L",
        roster_id="1",
        timestamp=NOW,
        lifecycle_transition="current->resolved",
        reason="resolved",
        category="Waivers",
        target_label="Bryce Ford-Wheaton",
        player_id="p1",
        destination="waivers",
        previous_state=None,
        current_state=None,
        summary_headline="Waiver opportunity resolved",
        summary_detail="Bryce Ford-Wheaton is no longer available in this league.",
        why_label="Recommendation no longer active",
        scoring_format="PPR",
        current_confidence_band="high",
    )
    payload.update(overrides)
    return history.DecisionChangeEvent(**payload)


def test_consumer_why_hides_internal_lifecycle_vocabulary():
    assert ui.consumer_why_label("Recommendation no longer active") == "Recommendation ended"
    assert ui.consumer_why_label("Lifecycle: Recommendation no longer active") == (
        "Recommendation ended"
    )
    assert ui.consumer_why_label("Strategy focus changed") == "Strategy focus changed"
    html = ui.decision_event_row_html(_event())
    assert "Lifecycle" not in html
    assert "Recommendation no longer active" not in html
    assert "Recommendation ended" in html
    assert "dg-dense-exception" not in html


def test_resolved_and_current_badges_are_not_truncated():
    resolved = ui.decision_event_row_html(_event())
    assert ">Resolved<" in resolved
    assert "Resolv" in resolved
    assert "Resolv..." not in resolved
    assert "data-what-changed-state='resolved'" in resolved
    current = ui.decision_event_row_html(
        _event(
            event_id="e-current",
            lifecycle_transition="new->current",
            why_label="",
            summary_headline="Start this week",
        )
    )
    assert ">Current<" in current
    assert "data-what-changed-state='current'" in current
    assert "dg-what-changed-item--current" in current


def test_long_player_name_and_copy_are_not_sliced():
    name = "Christopher Bartholomew Montgomery-Williams IV"
    detail = (
        "This waiver recommendation is no longer active because the player was "
        "claimed on another roster after the last Game Plan refresh."
    )
    html = ui.decision_event_row_html(
        _event(target_label=name, summary_detail=detail)
    )
    assert name in html
    assert detail in html
    assert "…" not in html


def test_mobile_css_stacks_status_and_unwraps_ellipsis():
    css = ui.DECISION_CHANGE_HISTORY_CSS
    compact = css.replace(" ", "").replace("\n", "")
    assert 'grid-template-areas:"id""metric""trail"' in compact
    assert "@media (max-width:640px)" in css
    assert "@media (min-width:641px)" in css
    assert "text-overflow:unset" in css
    assert "white-space:normal" in css
    assert "text-overflow:ellipsis" not in css
    assert ".dg-dense-metric__label{display:none}" in compact
    assert "@media (max-width:430px){.dg-decision-history-cta{max-width:none}}" not in css


def test_review_is_contained_footer_not_full_bleed():
    assert "use_container_width=False" in UI_SRC
    assert "use_container_width=True" not in UI_SRC
    assert "dg-decision-history-cta" in UI_SRC
    assert "dg_what_changed_card_" in UI_SRC
    assert "st-key-dg_what_changed_card_" in ui.DECISION_CHANGE_HISTORY_CSS


def test_desktop_keeps_side_by_side_columns():
    css = ui.DECISION_CHANGE_HISTORY_CSS
    desktop = css.split("@media (min-width:641px)", 1)[1]
    assert "grid-template-columns:minmax(0,1.4fr) max-content minmax(0,1fr)" in desktop
    # Dense list global sheet still owns non-What-Changed rows.
    from modules.dense_list_styles import DENSE_LIST_CSS

    assert "minmax(5.25rem,7rem)" in DENSE_LIST_CSS
    assert DENSE_LIST_CSS in APP_CSS
    assert ui.DECISION_CHANGE_HISTORY_CSS not in APP_CSS


def test_what_changed_css_stays_off_app_css():
    assert "dg-what-changed-item .dg-dense-metric__value" not in APP_CSS
    assert len(APP_CSS) < 390_000


def test_hydrate_placeholder_does_not_force_blank_scroll_height():
    block = DASHBOARD_WORKFLOW_CSS.split(".dashboard-hydrate-placeholder {", 1)[1]
    block = block.split(".dashboard-hydrate-kicker", 1)[0]
    lowered = block.casefold()
    assert "min-height" not in lowered
    assert "100vh" not in lowered
    assert "100dvh" not in lowered


def test_post294_player_refresh_has_one_canonical_dashboard_owner():
    assert APP.count("maybe_refresh_players_after_shell(") == 2
    football = APP.index('"football_context_ready"')
    dashboard = APP.index("render_home_dashboard(", football)
    refresh = APP.index("maybe_refresh_players_after_shell(", dashboard)
    dump = APP.index("_dash_wf.dump(", refresh)
    assert football < dashboard < refresh < dump
    pre = APP[football:dashboard]
    assert 'current_page) != "dashboard"' in pre
    assert "background=True" in APP[refresh : refresh + 400]
    # Must not call the GIL refresh builder before first useful on Dashboard.
    assert "build_players_table(refresh=True)" not in APP
    hydrate = APP.split("# --- Football hydration", 1)[1].split(
        "render_home_dashboard(", 1
    )[0]
    assert "maybe_refresh_players_after_shell(" not in hydrate or (
        'current_page) != "dashboard"' in hydrate
    )
