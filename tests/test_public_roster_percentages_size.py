"""ESPN's ownership payload exceeded the old 8 MB cap (~9.2 MB in Nov 2026), silently yielding no roster %."""

import json
from unittest.mock import MagicMock, patch

from modules import public_roster_percentages as prp


def _response(raw: bytes):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.iter_content.return_value = [raw[i : i + 65536] for i in range(0, len(raw), 65536)]
    resp.__enter__.return_value = resp
    return resp


def test_realistic_9mb_payload_is_parsed():
    player = {"player": {"id": 1, "fullName": "A B", "defaultPositionId": 3, "proTeamId": 1, "ownership": {"percentOwned": 12.5, "date": 1}, "pad": "x" * 9_000_000}}
    raw = json.dumps({"players": [player]}).encode()
    assert 9_000_000 < len(raw) <= prp.MAX_RESPONSE_BYTES
    prp.ownership_rows.cache_clear()
    with patch.object(prp.requests, "get", return_value=_response(raw)):
        rows = prp.ownership_rows(2026, 1)
    assert rows and rows[0]["percent"] == 12.5


def test_oversized_payload_still_rejected():
    prp.ownership_rows.cache_clear()
    with patch.object(prp.requests, "get", return_value=_response(b"x" * (prp.MAX_RESPONSE_BYTES + 1))):
        assert prp.ownership_rows(2026, 2) == []
