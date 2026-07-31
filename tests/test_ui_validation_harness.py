from pathlib import Path

from scripts.validate_mobile_ui import SURFACES, WIDTHS


ROOT = Path(__file__).resolve().parents[1]


def test_validation_matrix_covers_required_surfaces_and_widths():
    assert set(SURFACES) == {"dashboard", "league", "trade", "my-team"}
    assert WIDTHS == (320, 390, 430)


def test_harness_is_fixture_only_and_not_in_production_entrypoint():
    harness = (ROOT / "scripts" / "ui_validation_harness.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "ui_validation_harness" not in app_source
    assert "Synthetic fixture only" in harness
    for forbidden in ("access_token", "password", "auth_session", "customer"):
        assert forbidden not in harness.casefold()


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
