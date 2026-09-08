from unittest.mock import patch
import json
from pathlib import Path

import pytest
import requests

from conftest import frozen_trust_inputs, public_player_trust_fixture


@pytest.mark.parametrize("drift", ["fewer", "more"])
def test_trust_fixture_ignores_provider_and_disk_drift(tmp_path_factory, drift):
    root = Path(__file__).resolve().parents[1]
    live_inventory = json.loads((root / "data/sleeper_players.json").read_text())
    if drift == "fewer":
        live_inventory.clear()
    else:
        live_inventory["extra-live-player"] = {
            "full_name": "Extra Live Player", "position": "WR",
            "active": True, "years_exp": 0, "status": "Active",
        }
    with patch("modules.rankings.get_players", return_value=live_inventory) as provider, patch(
        "modules.structured_player_refresh.load_cached_players_disk",
        return_value=(live_inventory, 999),
    ) as disk:
        frame, _ = public_player_trust_fixture.__wrapped__(tmp_path_factory)
    assert len(frame) == 1880
    assert {"5199", "8058"} <= set(frame.player_id.astype(str))
    assert "extra-live-player" not in set(frame.player_id.astype(str))
    provider.assert_not_called()
    disk.assert_not_called()


def test_trust_fixture_rejects_even_swallowed_http():
    with pytest.raises(AssertionError, match="request"):
        with frozen_trust_inputs():
            try:
                requests.get("https://api.sleeper.app/v1/players/nfl")
            except AssertionError:
                pass
