"""Evidence-based injury return curves (docs/audits/2026-11-injury-discount.md, flag DYNASTYGM_INJURY_RETURN_CURVES_V1).

Replaces two static guesses with curves fitted on nflverse 2021-23 injury reports and weekly stats
(scripts/audits/injury_return_fit.py; the numbers live in the generated modules/injury_return_curves_table.py):

* ``expected_production_fraction``: share of a player's trailing PPG he is expected to produce over his next four team games
  (zeros for games missed). Used by redraft's current-availability multiplier instead of the severity bucket's flat factor.
* ``expected_games_lost``: games missed beyond what a healthy player misses, over the next 17. Used by the dynasty horizon model
  instead of the table's weeks_out only behind its own default-OFF switch (DYNASTYGM_INJURY_RETURN_CURVES_DYNASTY_V1).

Report-status "state" is one of Out / Doubtful / Questionable / IR (IR = PUP / NFI / season-ending / injured reserve). Anything else
(day-to-day, limited, probable, suspended, a bare "Inactive") has no fitted evidence and returns None so the caller keeps its legacy
number. The runtime flag path uses the pooled state curve: position, weeks-since-listing and body-group cells are fitted and
reported but did not beat it out of sample with a CI excluding zero, so they are only used when a caller passes them.

No import from rankings / trade code: base layer next to injury_status.
"""

from __future__ import annotations

from typing import Any

from modules import injury_return_curves_table as _t
from modules import injury_status as _status

ENV_KEY = "DYNASTYGM_INJURY_RETURN_CURVES_V1"
# Separate, default-OFF switch for feeding the fitted games lost into the dynasty horizon model (it did not beat the table out of
# sample on games-lost error, see the audit doc), so it does not ride on the redraft decision.
DYNASTY_FEED_ENV_KEY = "DYNASTYGM_INJURY_RETURN_CURVES_DYNASTY_V1"
HORIZON_GAMES = 4

_STATE_BY_ROW = {
    "out": "Out",
    "doubtful": "Doubtful",
    "questionable": "Questionable",
    "ir": "IR",
    "pup": "IR",
    "nfi": "IR",
    "season_ending": "IR",
}
_AGE_BUCKETS = (1, 2, 3, 4, 6, 8)


def enabled() -> bool:
    from modules.experimental_graduation import graduated_kill_switch_enabled

    return graduated_kill_switch_enabled(ENV_KEY, default=DEFAULT_ON)


def dynasty_feed_enabled() -> bool:
    from modules.app_config import config_bool

    return bool(config_bool(DYNASTY_FEED_ENV_KEY))


# Flag decision (docs/audits/2026-11-injury-discount.md, "Evidence-based return curves"): out of sample on 2024-25 the fitted curve
# beats the static current-season multiplier on next-4-game points error with a confidence interval that excludes zero.
DEFAULT_ON = True


def state_for(status: Any = "", injury_status: Any = "") -> str | None:
    """The fitted report state for a (roster status, Sleeper injury_status) pair, or None when there is no evidence for it."""

    return _STATE_BY_ROW.get(_status.classify(status, injury_status).row.key)


def age_bucket(weeks_since_listing: int) -> int:
    weeks = int(weeks_since_listing)
    for bucket, upper in ((1, 1), (2, 2), (3, 3), (4, 4), (6, 6)):
        if weeks <= upper:
            return bucket
    return 8


def _estimate(state: str, target: str, position: str | None, weeks_since_listing: int | None, body: str | None) -> float:
    pos = str(position or "").upper() or None
    if weeks_since_listing:
        bucket = age_bucket(weeks_since_listing)
        for table, key in ((_t.POS_STATE_AGE, (pos, state, bucket)), (_t.STATE_AGE, (state, bucket))):
            if key in table:
                return float(table[key][1][target])
    if body and pos and (pos, state, body) in _t.POS_STATE_BODY:
        return float(_t.POS_STATE_BODY[(pos, state, body)][1][target])
    if pos and (pos, state) in _t.POS_STATE:
        return float(_t.POS_STATE[(pos, state)][1][target])
    return float(_t.STATE[(state,)][1][target])


def expected_production_fraction(
    status: Any = "",
    injury_status: Any = "",
    *,
    position: str | None = None,
    weeks_since_listing: int | None = None,
    body: str | None = None,
) -> float | None:
    """Expected share of trailing PPG over the next four team games (None = no fitted evidence for this status)."""

    state = state_for(status, injury_status)
    if state is None:
        return None
    return max(0.0, min(1.0, _estimate(state, "f4", position, weeks_since_listing, body)))


def expected_games_lost(
    status: Any = "",
    injury_status: Any = "",
    *,
    position: str | None = None,
    weeks_since_listing: int | None = None,
    body: str | None = None,
) -> float | None:
    """Expected games missed over the next 17 beyond a healthy same-position player's own absences (None = no evidence)."""

    state = state_for(status, injury_status)
    if state is None:
        return None
    healthy = _t.HEALTHY_LOST17.get(str(position or "").upper(), _t.HEALTHY_LOST17["ALL"])
    return max(0.0, _estimate(state, "lost17", position, weeks_since_listing, body) - healthy)
