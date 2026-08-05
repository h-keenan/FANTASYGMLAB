"""Founder Beta launch-candidate production-readiness contracts."""

from pathlib import Path

from modules import launch_analytics


ROOT = Path(__file__).resolve().parents[1]
CUSTOMER_PATHS = (
    ROOT / "app.py",
    ROOT / "modules" / "account_ui.py",
    ROOT / "modules" / "feedback_ui.py",
    ROOT / "modules" / "notification_center.py",
    ROOT / "modules" / "premium_page.py",
)


def test_launch_analytics_events_are_all_wired():
    sources = "\n".join(path.read_text(encoding="utf-8") for path in CUSTOMER_PATHS)
    for event in sorted(launch_analytics.TRACKED_EVENTS):
        assert f'"{event}"' in sources or f"'{event}'" in sources, event


def test_customer_surfaces_avoid_developer_infrastructure_copy():
    banned = (
        "architecture supports",
        "feedback dashboard",
        "enabled in Supabase",
        "How the MVP may",
        "TODO",
        "FIXME",
        "lorem ipsum",
    )
    for path in CUSTOMER_PATHS:
        text = path.read_text(encoding="utf-8")
        lowered = text.casefold()
        for phrase in banned:
            assert phrase.casefold() not in lowered, f"{path.name}: {phrase}"


def test_trade_hub_launch_contract_remains_unified_feed():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    board = source[
        source.index("if current_page == \"trade_hub\":") : source.index(
            "# TRADE ANALYZER"
        )
        if "# TRADE ANALYZER" in source
        else source.index("if current_page == \"trade_analyzer\":")
    ]
    assert "trade_hub_opened" in board
    assert "annotate_trade_hub_feed_categories(" in board
    assert "render_trade_hub_section_filter(" not in board
    assert "st.pills(" not in board


def test_launch_candidate_report_documents_decision_and_blockers():
    docs = (ROOT / "docs" / "founder-beta-launch-candidate.md").read_text(encoding="utf-8")
    assert "Ready after listed manual tasks" in docs
    assert "LC0-P0" in docs
    assert "not cleared to charge real money" in docs.casefold() or "not ready to charge" in docs.casefold()
    assert "b59976d" in docs or "current main" in docs.casefold()
