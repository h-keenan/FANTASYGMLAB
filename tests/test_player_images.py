from __future__ import annotations

from unittest.mock import patch

from modules.player_images import fetch_player_headshot_bytes


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


def test_fetch_player_headshot_bytes_returns_none_after_two_real_failures():
    with patch(
        "modules.player_images.requests.get",
        side_effect=[_FakeResponse(404), _FakeResponse(404)],
    ), patch("modules.player_images.time.sleep"):
        result = fetch_player_headshot_bytes("4046")

    assert result is None
