"""Contracts for single-rerun handoff / quick-action destination navigation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_quick_actions_commit_without_explicit_rerun():
    source = (ROOT / "modules" / "workspace_ui.py").read_text(encoding="utf-8")
    start = source.index("def render_home_quick_actions")
    body = source[start:]
    assert "commit_platform_destination" in body
    assert "on_click=commit_platform_destination" in body
    assert "st.rerun()" not in body
    assert "queue_platform_route" not in body


def test_workspace_and_premium_handoffs_use_commit_callbacks():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for needle in (
        'kwargs={"source": "premium_lock"}',
        'kwargs={"source": "workspace_handoff"}',
        'kwargs={"source": "trade_workflow_handoff"}',
        'kwargs={"source": "profile_premium"}',
        "open_trade_hub_for_player=_open_trade_hub_from_live_draft_rank",
    ):
        assert needle in source
    handoff = source[
        source.index("def render_workspace_handoff") : source.index(
            "def render_trade_workflow_handoff"
        )
    ]
    trade = source[
        source.index("def render_trade_workflow_handoff") : source.index(
            "render_archetype_summary"
        )
    ]
    assert "st.rerun()" not in handoff
    assert "st.rerun()" not in trade


def test_live_draft_prefers_trade_hub_commit_callback():
    source = (ROOT / "modules" / "live_draft_ui.py").read_text(encoding="utf-8")
    assert "open_trade_hub_for_player" in source
    assert "on_click=open_trade_hub_for_player" in source
