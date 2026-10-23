from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from modules import dashboard_workflow, startup_coordinator


DASHBOARD_WORKFLOW_PATH = Path("modules/dashboard_workflow.py")


def test_startup_milestone_logging_emits_structured_line(capsys):
    state: dict = {}
    startup_coordinator.log_startup_milestone(state, "session_restored", started_at=0.0)

    captured = capsys.readouterr().out
    assert "DYNASTYGM_STARTUP" in captured
    assert "session_restored" in captured
    assert "Session restored" in captured
    assert "elapsed_ms" in captured
