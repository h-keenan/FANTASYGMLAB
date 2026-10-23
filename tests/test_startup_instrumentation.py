from pathlib import Path

from modules import runtime_trace


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
