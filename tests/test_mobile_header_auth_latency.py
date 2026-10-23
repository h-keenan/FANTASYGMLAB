"""Production mobile header + early account-control contracts."""

from __future__ import annotations

from pathlib import Path

from modules import startup_critical_path

ROOT = Path(__file__).resolve().parents[1]


def test_auth_storage_deadline_is_bounded_for_account_cta_latency():
    assert startup_critical_path.AUTH_STORAGE_CLIENT_DEADLINE_MS == 1_500
    assert startup_critical_path.AUTH_STORAGE_CLIENT_DEADLINE_MS < 3_000
