from pathlib import Path

from scripts.classify_pr_changes import UI_PATH_RULES, is_mobile_app_path, is_ui_path


ROOT = Path(__file__).resolve().parents[1]


def test_ui_path_classification_is_explicit_and_narrow():
    assert UI_PATH_RULES
    for path in (
        "app.py",
        "modules/trade_hub_ui.py",
        "modules/founder_beta_consistency_styles.py",
        "modules/application_shell.py",
        "scripts/ui_validation_harness.py",
        "tests/test_trade_summary_cards.py",
        ".github/workflows/ci.yml",
    ):
        assert is_ui_path(path), path
    for path in (
        "modules/trade_engine.py",
        "modules/player_valuation.py",
        "docs/valuation.md",
        "data/players.db",
    ):
        assert not is_ui_path(path), path


def test_mobile_app_path_classification_is_scoped_to_mobile_directory():
    for path in ("mobile/App.tsx", "mobile/src/lib/api.ts", "mobile/package.json"):
        assert is_mobile_app_path(path), path
    for path in ("app.py", "modules/trade_engine.py", "services/mobile_api_service.py"):
        assert not is_mobile_app_path(path), path


def test_ci_validates_mobile_app_directory_when_touched():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "needs.classify.outputs.mobile_app_changed == 'true'" in workflow
    assert "working-directory: mobile" in workflow
    assert "npm run typecheck" in workflow
    assert "npx expo-doctor" in workflow


def test_delivery_contract_requires_merge_completion():
    contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "latest `origin/main`" in contract
    assert "Enable auto-merge" in contract
    assert "final merge SHA" in contract
    assert "missing local browser connection" in contract


def test_ci_has_non_skippable_ui_artifacts_and_health_wait():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "playwright install --with-deps chromium" in workflow
    assert "/_stcore/health" in workflow
    assert "if-no-files-found: error" in workflow
    assert "ui-mobile-screenshots-" in workflow
    assert "needs.classify.outputs.ui_changed == 'true'" in workflow


def test_mobile_validator_uses_fixture_sections_and_ignores_heading_permalink_chrome():
    validator = (ROOT / "scripts" / "validate_mobile_ui.py").read_text(encoding="utf-8")
    assert 'get_attribute("data-ui-sections")' in validator
    assert "aria-label') !== 'Link to heading'" in validator
    assert 'data-testid="stHeaderActionElements"' in validator


def test_auto_merge_runs_only_from_trusted_completed_workflow():
    workflow = (ROOT / ".github" / "workflows" / "auto-merge.yml").read_text(encoding="utf-8")
    assert "workflow_run:" in workflow
    assert 'workflows: ["Delivery Validation"]' in workflow
    assert "human-approval-required" in workflow
    assert 'gh pr merge "$pr_number" --repo "$REPOSITORY" --merge' in workflow
    assert "workflow_run.conclusion == 'success'" in workflow
