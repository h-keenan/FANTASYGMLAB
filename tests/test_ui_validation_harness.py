from pathlib import Path

from scripts.validate_mobile_ui import SURFACES, WIDTHS


ROOT = Path(__file__).resolve().parents[1]


def test_validation_matrix_covers_required_surfaces_and_widths():
    assert set(SURFACES) == {
        "dashboard",
        "league",
        "trade",
        "my-team",
        "waivers",
        "navigation",
        "live-draft",
        "player-dossier",
    }
    assert WIDTHS == (320, 390, 430, 768, 1024, 1440)


def test_harness_is_fixture_only_and_not_in_production_entrypoint():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "ui_validation_harness" not in app_source
    assert "Synthetic fixture only" in harness
    for forbidden in ("access_token", "password", "auth_session", "customer"):
        assert forbidden not in harness.casefold()
    assert "dashboard_orientation.render_orientation_if_applicable(" in harness
    assert "persistently_dismissed=False" in harness


def test_validator_fails_closed_on_required_defect_classes():
    source = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    for contract in (
        "StreamlitDuplicateElementKey",
        "horizontal overflow",
        "primary heading is clipped",
        "near-zero-width primary content",
        "unusable tap targets",
        "missing section",
        "component frame unavailable",
        "trade summary too tall",
        "trade summary avatar below 44px visual target",
        "trade summary title is clipped",
        "visible Streamlit chrome",
        "unreclaimed top chrome space",
        "large rounded GM shell",
        "legacy GM gradient",
        "GM menu lacks internal scrolling",
        "undersized GM targets",
        "current route is not structurally highlighted",
        "noncanonical modal radius",
        "undersized modal close target",
    ):
        assert contract in source
    assert "except Exception: pass" not in source


def test_validator_captures_the_complete_single_dialog_trade_flow():
    validator = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    for screenshot in (
        "trade-detail-expanded-",
        "trade-player-dossier-",
        "trade-detail-returned-",
    ):
        assert screenshot in validator
    assert 'data-player-id="6794"' in validator
    assert 'name="Back to trade"' in validator
    assert "page.locator(selector).count()" in validator
    assert "render_player_dossier=dossier" in harness
    assert "player_cards.render_tappable_player_html" in harness


def test_validator_captures_collapsed_and_expanded_founder_navigation():
    validator = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert '"navigation": ("All Destinations", "Core", "Support")' in validator
    assert "navigation-expanded-" in validator
    assert "mobile-gm-floating-trigger-marker" in harness
    assert "mobile-gm-sheet-marker" in harness
    assert 'type="primary"' in harness


def test_validator_captures_canonical_dossier_progressive_disclosure():
    validator = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    assert '"player-dossier": (' in validator
    assert "player-dossier-history-expanded-" in validator
    assert "player-dossier-advanced-" in validator
    assert "player_history.build_career_resume(" in harness
    assert "View full career resume" in harness
