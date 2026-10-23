from contextlib import contextmanager
from pathlib import Path

from modules import trade_hub_presentation


def _idea(
    *,
    tag="Trade idea",
    confidence="Medium",
    strategy="retool",
    my_player="Send",
    their_player="Get",
    gain=100,
):
    return {
        "partner_roster_id": "2",
        "partner_team_name": "Partner",
        "my_player": my_player,
        "their_player": their_player,
        "my_score": 1000,
        "their_score": 1000 + gain,
        "trade_gain": gain,
        "tag": tag,
        "my_strategy": strategy,
        "partner_strategy": "retool",
        "trade_confidence_label": confidence,
        "market_realism_label": "Plausible",
        "fit_grade": "Solid",
        "send_assets": [{"asset_type": "player", "player_id": "1", "name": my_player}],
        "receive_assets": [{"asset_type": "player", "player_id": "2", "name": their_player}],
    }
