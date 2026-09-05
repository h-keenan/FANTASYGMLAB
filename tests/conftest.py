"""Opt-in deterministic data fixtures; no global production overrides."""

from hashlib import sha256
from pathlib import Path
import shutil

import pytest


@pytest.fixture
def cached_2025_stats_season(monkeypatch):
    """The committed valuation golden uses 2025 current / 2024 prior stats."""
    from modules import sleeper

    monkeypatch.setattr(sleeper, "default_player_stats_season", lambda: 2025)
    monkeypatch.setattr(sleeper, "prior_player_stats_season", lambda: 2024)


@pytest.fixture(scope="session")
def public_player_trust_fixture(tmp_path_factory):
    """Hydrate the current universe without rewriting the committed database."""
    from scripts.profile_trust_enforcement import _load_real_frame

    source = Path(__file__).resolve().parents[1] / "data" / "players.db"
    original_digest = sha256(source.read_bytes()).hexdigest()
    destination = tmp_path_factory.mktemp("trust-public-universe") / "players.db"
    shutil.copyfile(source, destination)
    frame, columns = _load_real_frame(str(destination))
    assert sha256(source.read_bytes()).hexdigest() == original_digest
    return frame, columns
