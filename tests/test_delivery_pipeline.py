from pathlib import Path

from scripts.classify_pr_changes import is_mobile_app_path, is_web_next_path


ROOT = Path(__file__).resolve().parents[1]


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


def test_ci_has_no_streamlit_browser_job():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "streamlit" not in workflow.lower()
    assert "_stcore" not in workflow
    assert "app.py" not in workflow


def test_change_classifier_recognizes_mobile_and_web_next_paths():
    assert is_mobile_app_path("mobile/src/App.tsx")
    assert is_web_next_path("web-next/src/app/page.tsx")
    assert not is_mobile_app_path("services/mobile_api_service.py")


def test_auto_merge_runs_only_from_trusted_completed_workflow():
    workflow = (ROOT / ".github" / "workflows" / "auto-merge.yml").read_text(encoding="utf-8")
    assert "workflow_run:" in workflow
    assert 'workflows: ["Delivery Validation"]' in workflow
    assert "human-approval-required" in workflow
    assert 'gh pr merge "$pr_number" --repo "$REPOSITORY" --merge' in workflow
    assert "workflow_run.conclusion == 'success'" in workflow
