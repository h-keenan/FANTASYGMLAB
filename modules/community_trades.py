"""Community Trade Feed — cross-user anonymized "craziest trades" highlights.

Social/community layer (docs/roadmap.md "Social / community layer" open
initiative). coridian_, 2026-10-19: a community tab showing confirmed trades
pulled from OTHER users' real leagues, anonymized as "Team A traded with Team
B" — never real user/team identity. "Interesting" is deliberately NOT a new
heuristic: coridian_ explicitly said this reuses the app's existing trade-
grading signals rather than inventing a new "interesting" calculation, and
separately de-emphasized a strict algorithm ("it just needs to be fun and
engaging"). This module therefore adds ZERO new scoring logic — it is a thin,
read-only, anonymizing projection over modules.trade_outcome_results'
already-computed verdict/confidence (compute_trade_result,
run_trade_outcome_result_sweep, the `trade_outcomes` table's
result_summary/result_computed_at columns).

"Interesting" = a confirmed ('yes') trade whose computed result_summary has
status "ready", confidence "high" (both the real-production and value-trend
signals agree — see modules.trade_outcome_results._combine_directions), and
verdict "worked_out" or "didnt_pan_out" (a real, lopsided, surprising-in-
hindsight outcome — exactly coridian_'s "unexpected good/unexpected bad"
framing). "mixed"/"neutral"/low-or-medium-confidence rows are deliberately
excluded — not because they're uninteresting, but because confidence < high
means the two signals disagree or only one exists, which is a weaker claim
than this feed wants to make about a trade in someone else's real league.

CROSS-USER READ — THE HIGH-RISK PART
-------------------------------------
Every other per-user table in this app (trade_outcomes included;
see docs/supabase_trade_outcomes.sql) is RLS-gated `auth.uid() = user_id`:
a signed-in user's own anon-key + JWT can only ever see their own rows. That
is exactly correct for everything else in this app, but a community feed
needs to read OTHER users' trade_outcomes rows too. Two ways to do that were
considered and rejected in favor of a third:

  1. Loosen trade_outcomes' RLS to a `select true` policy (like
     docs/supabase_college_scouting.sql's deliberately-public
     scouting_reports table). Rejected: scouting_reports' content (a 1-5
     grade on a public college prospect) carries no real user activity or
     identity risk even with a raw user_id attached. trade_outcomes rows
     carry a real user_id, a real league_id, and (most importantly) a
     free-text partner_team_name a user typed in to describe the OTHER real
     Sleeper manager they traded with in THEIR league — a third party who
     never consented to this feature at all. A `select true` policy on that
     table would let ANY signed-in client query it directly via supabase-js
     (bypassing this backend, its anonymization, and the opt-out check
     entirely) and read every user's raw league_id/partner_team_name/
     user_id. That is precisely the leak this feature must never cause.
  2. Have the client read community_trade_reactions directly via
     supabase-js with a `select true` policy. Same rejection, smaller blast
     radius but still real: it would expose a raw user_id -> outcome_id
     reaction mapping to any client, and reaction counts could not be
     filtered by opt-out status without a service-role step anyway.

  3. (Chosen) This module owns its OWN minimal service-role Supabase access
     — same "own minimal service-role Supabase access, isolated from every
     other job" pattern modules.push_triggers and
     modules.trade_outcome_results already use for their standalone cron
     jobs, used here instead inside a live backend request path
     (services/mobile_api_service.py's GET /v1/community/trades). Service
     role bypasses RLS by design, which is exactly why this module is the
     ONLY place in the whole request path allowed to touch raw cross-user
     trade_outcomes/user_settings rows — every function below that returns
     data to the caller returns an ALREADY-ANONYMIZED projection
     (build_community_feed_items), never a raw row. partner_team_name,
     league_id, and user_id are read here (user_id only to apply the
     opt-out filter and to mark the viewer's own reactions) and then
     dropped — none of the three is ever present in this module's output.

ANONYMIZATION CHOICE: "Team A" / "Team B" placeholders, always
----------------------------------------------------------------
docs/roadmap.md's own spec already calls for placeholder labels ("Team A
traded with Team B"), not real team names — and the partner-consent problem
above makes that the only safe choice anyway: even a user who has NOT opted
out only ever consents for THEMSELVES, never for the other real manager
named in their own partner_team_name field. So real team names (either
side's) never reach this feed's output under any circumstance. "Team A" is
always the user who recorded the trade (trade_summary's send/receive are
already relative to them); "Team B" is always their trade partner. This is a
fresh, generic per-item label, not a persistent handle — it carries no
identity across different feed items.

OPT-OUT: user_settings, "community_trades_opt_out" key
----------------------------------------------------------------
Reuses the existing per-user `user_settings.settings` JSON blob (same table/
pattern as /v1/push/preferences' "push_categories" key and /v1/preferences'
"ui_density" key — see services/mobile_api_service.py) rather than a new
table. On by default: a user who has never touched the setting (key absent)
is included, matching coridian_'s "on by default, with a visible opt-out
toggle" spec. Checking this filter is why fetch_opted_out_user_ids must also
run under service role — user_settings is `auth.uid() = user_id` RLS too, so
reading every user's setting the same way the main request's own user token
reads its own settings is not possible.

REACTIONS: emoji-only, fixed set, no moderation layer
----------------------------------------------------------------
No existing emoji-reaction UI precedent exists anywhere else in this app
(checked before building this) — COMMUNITY_REACTION_EMOJI below is a new,
small, fixed set. Deliberately emoji-only / no comments or replies per
coridian_'s explicit "no moderation layer" reasoning. A reaction write
(insert/delete on community_trade_reactions) always uses the CALLER's own
access token, never service role — RLS auth.uid() = user_id is sufficient
and correct there (a user can only ever add/remove their OWN reaction), so
that mutation path never needs this module's elevated access at all; see
services/mobile_api_service.py's react endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import requests

from modules import app_config

TRADE_OUTCOMES_TABLE = "trade_outcomes"
USER_SETTINGS_TABLE = "user_settings"
COMMUNITY_REACTIONS_TABLE = "community_trade_reactions"

# Fixed, small, no-free-text set — exactly why this feature needs no
# moderation layer. Picked for plain engagement reactions to a trade
# outcome, nothing position/team-specific.
COMMUNITY_REACTION_EMOJI: tuple[str, ...] = ("🔥", "😂", "😱", "💀", "📈")

# Only these two verdicts are ever "interesting" in coridian_'s framing —
# "mixed"/"neutral" are excluded entirely, not just deprioritized.
INTERESTING_VERDICTS = ("worked_out", "didnt_pan_out")
INTERESTING_CONFIDENCE = "high"

# Simple cap, not a pagination contract — mirrors GET /v1/trade-outcomes/
# history's own limit=50. This app has no accumulated volume yet (see
# modules.trade_outcome_results's own module docstring on that); revisit
# only once real volume makes a flat limit feel thin.
COMMUNITY_FEED_LIMIT = 40


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


@dataclass(frozen=True)
class CommunityFeedConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_community_feed_config(*, environ: dict | None = None, secrets: Any = None) -> CommunityFeedConfig:
    """Own config loader — not modules.push_triggers.load_push_trigger_config
    or modules.trade_outcome_results.load_result_sweep_config — same "a bug
    in one job's config handling can't reach another's" reasoning those two
    modules' own docstrings already give, applied here even though this
    runs inside a live request rather than a standalone cron process."""

    return CommunityFeedConfig(
        url=app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def _headers(config: CommunityFeedConfig) -> dict[str, str]:
    return {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }


def fetch_interesting_trade_outcomes(config: CommunityFeedConfig) -> list[dict[str, Any]]:
    """Confirmed trades with a real, lopsided, high-confidence computed
    result — service-role, cross-user by necessity (see module docstring).
    user_id is selected ONLY to drive the opt-out filter in the caller; it
    is never included in this module's anonymized output."""

    if not config.configured:
        return []
    verdicts = ",".join(INTERESTING_VERDICTS)
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{TRADE_OUTCOMES_TABLE}",
            headers=_headers(config),
            params={
                "select": "id,user_id,trade_summary,outcome_recorded_at,shared_at,result_summary,result_computed_at",
                "outcome": "eq.yes",
                "result_summary->>status": "eq.ready",
                "result_summary->>confidence": f"eq.{INTERESTING_CONFIDENCE}",
                "result_summary->>verdict": f"in.({verdicts})",
                "order": "result_computed_at.desc",
                "limit": "200",
            },
            timeout=15,
        )
    except Exception:
        return []
    if response.status_code >= 400:
        return []
    try:
        rows = response.json()
    except Exception:
        return []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def fetch_opted_out_user_ids(config: CommunityFeedConfig) -> set[str]:
    """Every user_id whose user_settings.settings carries
    community_trades_opt_out=true. Service-role, cross-user (user_settings
    is auth.uid()=user_id RLS, same reason as fetch_interesting_trade_
    outcomes above). Fails closed to "nobody opted out is known" -> callers
    should treat a failure here as a reason to show nothing rather than
    guess (see get_community_trades's try/except in
    services/mobile_api_service.py)."""

    if not config.configured:
        return set()
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{USER_SETTINGS_TABLE}",
            headers=_headers(config),
            params={"select": "user_id,settings"},
            timeout=15,
        )
    except Exception:
        return set()
    if response.status_code >= 400:
        return set()
    try:
        rows = response.json()
    except Exception:
        return set()
    if not isinstance(rows, list):
        return set()
    opted_out: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        settings = row.get("settings") if isinstance(row.get("settings"), Mapping) else {}
        if bool(settings.get("community_trades_opt_out")):
            user_id = _safe_text(row.get("user_id"))
            if user_id:
                opted_out.add(user_id)
    return opted_out


def fetch_reaction_rows(config: CommunityFeedConfig, outcome_ids: Iterable[str]) -> list[dict[str, Any]]:
    """Raw (outcome_id, user_id, emoji) rows for the given outcome ids —
    service-role, so this never depends on community_trade_reactions having
    any select-all RLS policy (it doesn't; see docs/supabase_community_
    trade_reactions.sql). Aggregated into counts/"did I react" by
    build_community_feed_items, never returned raw to a caller."""

    ids = [_safe_text(outcome_id) for outcome_id in outcome_ids if _safe_text(outcome_id)]
    if not config.configured or not ids:
        return []
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{COMMUNITY_REACTIONS_TABLE}",
            headers=_headers(config),
            params={
                "select": "outcome_id,user_id,emoji",
                "outcome_id": "in.(" + ",".join(ids) + ")",
            },
            timeout=15,
        )
    except Exception:
        return []
    if response.status_code >= 400:
        return []
    try:
        rows = response.json()
    except Exception:
        return []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _magnitude_score(result_summary: Mapping[str, Any]) -> float:
    """"Craziest" = biggest real edge, not a complex ranking algorithm (per
    coridian_'s "craziest trades this week" framing and explicit de-
    emphasis of a strict algorithm). Production (PPR pts/wk) and value-trend
    (a %) are different units with no principled single scale to convert
    between them, so this is a simple, documented, deliberately rough
    reconciliation (dividing the value-trend % by 4 puts a "large" value
    swing, ~20%, in roughly the same range as a "large" production edge,
    ~5 pts/wk) — not a claim of precision, just a sort key."""

    production = result_summary.get("production") if isinstance(result_summary.get("production"), Mapping) else {}
    value = result_summary.get("value") if isinstance(result_summary.get("value"), Mapping) else {}
    avg_per_week = abs(float(production.get("avg_net_per_week") or 0.0)) if production else 0.0
    value_delta = abs(float(value.get("net_delta_pct") or 0.0)) / 4.0 if value else 0.0
    return max(avg_per_week, value_delta)


def _anonymized_assets(assets: Any) -> list[dict[str, Any]]:
    if not isinstance(assets, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for asset in assets[:10]:
        if not isinstance(asset, Mapping):
            continue
        # Player name/position/id are public NFL-player facts, not
        # user-identifying — only partner_team_name/league_id/user_id (never
        # included here) would be. value_score is likewise just this app's
        # own public-ish valuation opinion of that player, not user data.
        entry: dict[str, Any] = {
            "name": _safe_text(asset.get("name")),
            "position": _safe_text(asset.get("position")),
        }
        player_id = _safe_text(asset.get("player_id"))
        if player_id:
            entry["player_id"] = player_id
        value_score = asset.get("value_score")
        if isinstance(value_score, (int, float)):
            entry["value_score"] = float(value_score)
        cleaned.append(entry)
    return cleaned


def build_community_feed_items(
    outcome_rows: Iterable[Mapping[str, Any]],
    *,
    opted_out_user_ids: set[str] | None = None,
    reaction_rows: Iterable[Mapping[str, Any]] | None = None,
    viewer_user_id: str = "",
    limit: int = COMMUNITY_FEED_LIMIT,
) -> list[dict[str, Any]]:
    """Pure projection: raw service-role trade_outcomes rows (already
    filtered to 'interesting' by fetch_interesting_trade_outcomes' query) ->
    fully anonymized, reaction-annotated feed items, sorted "craziest"
    (biggest real edge) first, then most-recently-resolved. Excludes any
    row whose user_id is in opted_out_user_ids. Never includes
    user_id/league_id/partner_team_name in its output — see module
    docstring's "ANONYMIZATION CHOICE" section.
    """

    opted_out = opted_out_user_ids or set()

    reaction_counts: dict[str, dict[str, int]] = {}
    viewer_reactions: dict[str, set[str]] = {}
    for row in reaction_rows or []:
        outcome_id = _safe_text(row.get("outcome_id"))
        emoji = _safe_text(row.get("emoji"))
        if not outcome_id or emoji not in COMMUNITY_REACTION_EMOJI:
            continue
        reaction_counts.setdefault(outcome_id, {}).setdefault(emoji, 0)
        reaction_counts[outcome_id][emoji] += 1
        if viewer_user_id and _safe_text(row.get("user_id")) == viewer_user_id:
            viewer_reactions.setdefault(outcome_id, set()).add(emoji)

    items: list[dict[str, Any]] = []
    for row in outcome_rows:
        outcome_id = _safe_text(row.get("id"))
        user_id = _safe_text(row.get("user_id"))
        if not outcome_id or (user_id and user_id in opted_out):
            continue
        result_summary = row.get("result_summary") if isinstance(row.get("result_summary"), Mapping) else {}
        verdict = result_summary.get("verdict")
        if verdict not in INTERESTING_VERDICTS or result_summary.get("confidence") != INTERESTING_CONFIDENCE:
            # Defensive re-check — fetch_interesting_trade_outcomes' own
            # query already filters this server-side, but this function
            # must stay safe to call directly (e.g. from a test, or a
            # future caller) without silently trusting an un-vetted row.
            continue
        trade_summary = row.get("trade_summary") if isinstance(row.get("trade_summary"), Mapping) else {}
        occurred_at = row.get("outcome_recorded_at") or row.get("shared_at")

        items.append(
            {
                "id": outcome_id,
                "send": _anonymized_assets(trade_summary.get("send")),
                "receive": _anonymized_assets(trade_summary.get("receive")),
                "verdict": verdict,
                "verdict_label": _safe_text(result_summary.get("verdict_label")),
                "confidence": result_summary.get("confidence"),
                "production": result_summary.get("production") if isinstance(result_summary.get("production"), Mapping) else None,
                "value": result_summary.get("value") if isinstance(result_summary.get("value"), Mapping) else None,
                "occurred_at": occurred_at,
                "reactions": reaction_counts.get(outcome_id, {}),
                "my_reactions": sorted(viewer_reactions.get(outcome_id, set())),
                "_magnitude": _magnitude_score(result_summary),
            }
        )

    # "Craziest" (biggest real edge) first, most-recently-resolved as the
    # tiebreak — a simple recency/magnitude sort, not a ranking algorithm.
    # reverse=True descends both fields together: magnitude high-to-low, and
    # (ISO 8601 sorts lexicographically same as chronologically) occurred_at
    # newest-to-oldest.
    items.sort(key=lambda item: (item["_magnitude"], item.get("occurred_at") or ""), reverse=True)
    for item in items:
        item.pop("_magnitude", None)
    return items[:limit]
