"""Prepare the deterministic local public-player cache during deployment build.

This consumes only checked-in SQLite/JSON/CSV inputs. Network/provider rebuilds
are hard-failed so deployment preparation cannot change provider semantics.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import rankings


DB_PATH = "data/players.db"


def prepare_public_player_cache(db_path: str = DB_PATH) -> dict[str, object]:
    if not Path(db_path).is_file():
        raise RuntimeError("canonical player SQLite seed is missing")

    original_builder = rankings.build_players_table

    def _network_build_forbidden(*_args, **_kwargs):
        raise RuntimeError("deployment cache preparation attempted a provider rebuild")

    rankings.build_players_table = _network_build_forbidden
    try:
        rankings.clear_public_player_cache()
        before = rankings.public_player_source_fingerprint(db_path)
        first = rankings.load_players(db_path)
        after_prepare = rankings.public_player_source_fingerprint(db_path)
        rankings.clear_public_player_cache()
        second = rankings.load_players(db_path)
        after_verify = rankings.public_player_source_fingerprint(db_path)
    finally:
        rankings.build_players_table = original_builder

    if first.empty or second.empty:
        raise RuntimeError("prepared public-player cache is empty")
    first_ids = tuple(first["player_id"].fillna("").astype(str))
    second_ids = tuple(second["player_id"].fillna("").astype(str))
    if first_ids != second_ids:
        raise RuntimeError("prepared public-player identities are not deterministic")
    if after_prepare != after_verify:
        raise RuntimeError("prepared public-player fingerprint did not stabilize")
    if str(second.attrs.get("public_player_load_path")) != "metadata_current_sqlite":
        raise RuntimeError("prepared cache did not reach metadata-current fast path")

    return {
        "rows": len(second),
        "fingerprint_changed_during_prepare": before != after_prepare,
        "load_path": second.attrs.get("public_player_load_path"),
        "provider_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(prepare_public_player_cache(), sort_keys=True))
