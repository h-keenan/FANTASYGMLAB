from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_polish_roadmap_covers_every_requested_destination_and_severity():
    roadmap = source("docs/founder-beta-polish-roadmap.md")
    for destination in (
        "Dashboard",
        "My Team",
        "League Rankings",
        "Rankings",
        "Trade Hub",
        "Waivers",
        "Startup Draft Center",
        "Live Draft",
        "Premium",
        "Workspace",
        "Settings / Account",
        "Feedback",
        "Login / Signup",
        "League picker",
    ):
        assert destination in roadmap
    for severity in ("## Critical", "## High", "## Medium backlog", "## Low backlog"):
        assert severity in roadmap
