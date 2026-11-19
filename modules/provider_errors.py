"""Typed provider errors for league import and sync (audit: docs/audits/2026-11-league-import-error-paths.md).

Before this module a Sleeper outage, a rate limit and a genuinely empty or unknown league all collapsed to ``[]`` / ``{}`` /
``None``, so the API told the user "Connect a league" or "League not found" when Sleeper was merely down. Strict readers in
``modules.sleeper`` raise these instead; the API maps them to 503 / 429 / 404 with a specific message and ``Retry-After``.

Kill switch: DYNASTYGM_PROVIDER_TYPED_ERRORS_V1 (default on). Off restores the legacy swallow-to-empty behaviour.
"""

from __future__ import annotations

TYPED_ERRORS_FLAG = "DYNASTYGM_PROVIDER_TYPED_ERRORS_V1"
ROSTER_SANITIZE_FLAG = "DYNASTYGM_ROSTER_PAYLOAD_SANITIZE_V1"
STALE_SNAPSHOT_FLAG = "DYNASTYGM_STALE_SNAPSHOT_ON_FAILED_REFRESH_V1"


def flag_enabled(key: str) -> bool:
    from modules.experimental_graduation import graduated_kill_switch_enabled

    return graduated_kill_switch_enabled(key)


def typed_errors_enabled() -> bool:
    return flag_enabled(TYPED_ERRORS_FLAG)


class ProviderError(RuntimeError):
    """A provider (Sleeper) read failed. ``reason`` is a stable client code; ``message`` is user-safe."""

    reason = "provider_error"
    status_code = 502
    retryable = True
    default_message = "We could not load your league data. Please try again."

    def __init__(self, message: str | None = None, *, detail: str = ""):
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.detail = detail  # internal failure kind, never shown to users


class ProviderUnavailableError(ProviderError):
    reason = "provider_unavailable"
    status_code = 503
    default_message = "Sleeper is temporarily unreachable. Wait a moment and try again."


class ProviderRateLimitedError(ProviderError):
    reason = "provider_rate_limited"
    status_code = 429
    default_message = "Sleeper is limiting requests right now. Try again in a minute."


class ProviderBadResponseError(ProviderError):
    reason = "provider_bad_response"
    status_code = 502
    default_message = "Sleeper sent back something we could not read. Try again in a moment."


class LeagueNotFoundError(ProviderError):
    reason = "league_not_found"
    status_code = 404
    retryable = False
    default_message = "League not found."


def error_for_failure(kind: str | None) -> ProviderError:
    """Map a recorded failure kind (modules.sleeper._request_json) to a typed error. Unknown means unavailable (retryable)."""

    kind = str(kind or "")
    if kind in {"http_429"}:
        return ProviderRateLimitedError(detail=kind)
    if kind in {"non_json_body", "bad_shape"}:
        return ProviderBadResponseError(detail=kind)
    if kind in {"null_body", "http_404", "http_400"}:
        return LeagueNotFoundError(detail=kind)
    return ProviderUnavailableError(detail=kind or "unknown")
