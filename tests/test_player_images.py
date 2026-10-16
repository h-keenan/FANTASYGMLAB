from __future__ import annotations

from unittest.mock import patch

from modules.player_images import fetch_player_headshot_bytes


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


def test_fetch_player_headshot_bytes_retries_once_after_a_transient_failure():
    """A single bad response (timeout, non-200) must not be the final word —
    cached_headshot_data_url (app.py) caches a `None` result for 24h, so one
    retry here is what keeps a one-off network blip from reading as "this
    player has no photo" sitewide for a full day (coridian_, Player Quick
    View showing an initials fallback for a player whose photo rendered
    fine elsewhere, 2026-10-16)."""
    responses = [Exception("boom"), _FakeResponse(200, b"jpegbytes")]

    def fake_get(_url, timeout):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with patch("modules.player_images.requests.get", side_effect=fake_get), patch(
        "modules.player_images.time.sleep"
    ):
        result = fetch_player_headshot_bytes("4046")

    assert result is not None
    assert result.getvalue() == b"jpegbytes"


def test_fetch_player_headshot_bytes_returns_none_after_two_real_failures():
    with patch(
        "modules.player_images.requests.get",
        side_effect=[_FakeResponse(404), _FakeResponse(404)],
    ), patch("modules.player_images.time.sleep"):
        result = fetch_player_headshot_bytes("4046")

    assert result is None
