"""Trade Outcomes — quiet "did it actually work?" result computation.

Separate, deliberately quiet sequel to modules/push_triggers.py's existing
"did this trade happen?" follow-up loop. That loop only asks whether a
shared trade was made (yes/no/didn't send/still pending) — it says nothing
about whether the trade was actually *good* for the user once it's had time
to play out. Per coridian_'s explicit brief: build the real follow-up, but
keep it quiet — no new push notification, no new popup. This module owns
only the *computation*; results are exposed exclusively through a pull-based
mobile endpoint (GET /v1/trade-outcomes/history in
services/mobile_api_service.py) that the mobile Trade History screen reads
when the user goes looking. Nothing here ever sends a push or triggers any in-app prompt.

Standalone Render Cron Job (scripts/run_trade_outcome_result_sweep.py, see
render.yaml's fantasygm-lab-trade-outcome-result-sweep entry), same
"own minimal service-role Supabase access" pattern modules/push_triggers.py
and modules/revenuecat_webhook.py already use — a bug here can't affect the
push-trigger sweep or vice versa. Run on its own daily schedule (not the
push sweep's */30 * * * *) because, unlike that sweep, a real run here loads
the full player rankings table and a season of Sleeper weekly stats — both
already-cached, but there's no reason to pay even the cache-hit cost every
30 minutes for a job that, by definition, only ever has new work once a
trade crosses a multi-week delay.

What gets evaluated:
    Only trade_outcomes rows the user themselves confirmed really happened
    (outcome == 'yes'), and only once RESULT_DELAY_DAYS have passed since
    that confirmation — "a few weeks", not immediately, so there's actually
    real production/valuation signal to look at (see module docstring on
    modules.player_projections for the same "don't claim precision you
    don't have" ethos this follows). Each row is evaluated **once**:
    result_computed_at is stamped whether or not a real verdict could be
    reached, so a permanently-unresolvable row (e.g. shared before this
    schema addition, so it carries no player_id) is never retried forever.

Data backing the comparison (both real, both already flowing through this
codebase — nothing fabricated):
    1. Value-score trend — trade_summary now optionally carries each
       tracked asset's player_id and the value_score visible to the user at
       share time (under whichever valuation_lens they had selected), via
       mobile/src/components/TradeSharePreviewModal.tsx. This sweep
       re-values the same players under the *same* lens (see
       modules.league_value_settings) and compares baseline vs current.
    2. Real production — modules.sleeper.get_season_player_stats's retained
       weekly PPR fantasy-points rows for each tracked player, summed over
       their most recent games since the trade. This is the more concrete,
       assumption-free signal (no valuation model involved at all), so it's
       the primary driver of the verdict; value-score trend is secondary,
       corroborating context.

Both signals are optional and independently gated — a row with only one
signal (e.g. a player_id present but no season stats yet) still gets a
low-confidence verdict from whichever signal exists; a row with neither
gets no verdict at all (status="insufficient_data"), which the mobile
Trade History screen simply renders without a result section. No verdict
is ever forced.

Feeding this back into trade recommendations (modules.trade_ideas) is
deliberately NOT done here. This tracking mechanism is brand new — at
launch there is no accumulated history of computed results for any user,
let alone enough per trade-type (buy-low/sell-high/consolidation) to
honestly say "this type of trade tends to work out for you." Wiring
fabricated pattern-recognition off of one or two data points would be
exactly the kind of dishonest verdict this module is built to avoid.
Once real volume accumulates, a future pass can look at
result_summary.verdict grouped by trade_summary shape and feed a real
signal back in — this module just needs to keep running long enough first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import pandas as pd
import requests

from modules import app_config, league_value_settings, player_eligibility, rankings, sleeper

PLAYERS_DB_PATH = "data/players.db"
TRADE_OUTCOMES_TABLE = "trade_outcomes"
DEFAULT_LENS = "Dynasty"

# "A few weeks", per the brief — long enough for real production data to
# exist, short enough that the user still remembers the trade when they see
# a result. Independent of, and much longer than, the existing 20h
# "did this happen?" follow-up delay in modules.push_triggers — this sweep
# never touches that constant or that sweep's behavior.
RESULT_DELAY_DAYS = 28
MAX_WEEKS_CONSIDERED = 8

# Thresholds below which a delta reads as noise rather than a real signal —
# deliberately conservative so a marginal edge doesn't get dressed up as a
# confident verdict.
PRODUCTION_THRESHOLD_PER_WEEK = 2.5  # net PPR pts/week edge
VALUE_DELTA_THRESHOLD_PCT = 8.0  # net value_score % edge


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN
        return None
    return result


@dataclass(frozen=True)
class ResultSweepConfig:
    url: str = ""
    service_role_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_result_sweep_config(*, environ: dict | None = None, secrets: Any = None) -> ResultSweepConfig:
    """Own config loader (not modules.push_triggers.load_push_trigger_config)
    — same reasoning as that module's own docstring: this runs as its own
    standalone cron process, so a bug in one job's config handling can't
    reach the other's."""

    return ResultSweepConfig(
        url=app_config.config_value("SUPABASE_URL", environ=environ, secrets=secrets),
        service_role_key=app_config.config_value("SUPABASE_SERVICE_ROLE_KEY", environ=environ, secrets=secrets),
    )


def _headers(config: ResultSweepConfig, *, prefer: str = "") -> dict[str, str]:
    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def fetch_pending_trade_outcome_results(config: ResultSweepConfig) -> list[dict[str, Any]]:
    """Confirmed ('yes') trade_outcomes rows old enough to evaluate and not
    yet computed (service-role, cross-user)."""

    if not config.configured:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RESULT_DELAY_DAYS)).isoformat()
    try:
        response = requests.get(
            f"{config.url}/rest/v1/{TRADE_OUTCOMES_TABLE}",
            headers=_headers(config),
            params={
                "select": "id,user_id,league_id,trade_summary,outcome_recorded_at",
                "outcome": "eq.yes",
                "result_computed_at": "is.null",
                "outcome_recorded_at": f"lte.{cutoff}",
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


def store_trade_outcome_result(config: ResultSweepConfig, *, outcome_id: str, result_summary: dict[str, Any]) -> None:
    """Stamp the computed (or permanently inconclusive) result. Never
    retried again once this succeeds — see module docstring."""

    if not config.configured or not outcome_id:
        return
    try:
        requests.patch(
            f"{config.url}/rest/v1/{TRADE_OUTCOMES_TABLE}",
            headers=_headers(config, prefer="return=minimal"),
            params={"id": f"eq.{outcome_id}"},
            json={
                "result_summary": result_summary,
                "result_computed_at": datetime.now(timezone.utc).isoformat(),
            },
            timeout=15,
        )
    except Exception:
        pass


def _asset_list(trade_summary: Mapping[str, Any], side: str) -> list[dict[str, Any]]:
    assets = trade_summary.get(side)
    if not isinstance(assets, list):
        return []
    return [asset for asset in assets if isinstance(asset, Mapping)]


def _tracked_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [asset for asset in assets if _safe_text(asset.get("player_id"))]


def weeks_elapsed_for(days_since_trade: int | None) -> int:
    days = days_since_trade if days_since_trade is not None else RESULT_DELAY_DAYS
    return max(1, min(MAX_WEEKS_CONSIDERED, days // 7))


def _side_production(
    assets: list[dict[str, Any]],
    season_stats: Mapping[str, Any],
    weeks_elapsed: int,
) -> dict[str, Any]:
    """Real PPR points these tracked players actually scored, over their own
    most recent `weeks_elapsed` games with recorded stats — an approximation
    of "since the trade" by recency rather than an exact trade-date week
    lookup (this codebase has no ready trade-date -> NFL-week mapping; see
    modules.player_projections's own documented "don't over-claim precision"
    pattern). A bye/inactive week simply isn't in a player's weekly list, so
    it doesn't unfairly zero out their total."""

    total_points = 0.0
    max_weeks_counted = 0
    any_data = False
    players: list[dict[str, Any]] = []
    for asset in _tracked_assets(assets):
        player_id = _safe_text(asset.get("player_id"))
        weekly = ((season_stats.get(player_id) or {}) if isinstance(season_stats.get(player_id), Mapping) else {})
        weekly_rows = weekly.get("weekly") if isinstance(weekly, Mapping) else None
        rows = [row for row in (weekly_rows or []) if isinstance(row, Mapping) and isinstance(row.get("week"), (int, float))]
        rows.sort(key=lambda row: row["week"], reverse=True)
        recent = rows[:weeks_elapsed]
        points = sum(float(row.get("fantasy_points_ppr") or 0.0) for row in recent)
        if recent:
            any_data = True
        total_points += points
        max_weeks_counted = max(max_weeks_counted, len(recent))
        players.append(
            {
                "player_id": player_id,
                "name": _safe_text(asset.get("name")),
                "points_ppr": round(points, 1),
                "weeks_counted": len(recent),
            }
        )
    return {
        "points_ppr": round(total_points, 1),
        "weeks_counted": max_weeks_counted,
        "players": players,
        "has_data": any_data,
    }


def _side_value(assets: list[dict[str, Any]], current_value_by_player: Mapping[str, float]) -> dict[str, Any]:
    """Baseline (share-time) vs current value_score for tracked assets where
    both are available — legacy assets missing either are simply excluded
    from the total rather than treated as zero."""

    baseline_total = 0.0
    current_total = 0.0
    matched = 0
    for asset in _tracked_assets(assets):
        baseline = _safe_float(asset.get("value_score"))
        current = _safe_float(current_value_by_player.get(_safe_text(asset.get("player_id"))))
        if baseline is None or current is None:
            continue
        baseline_total += baseline
        current_total += current
        matched += 1
    return {"baseline": round(baseline_total, 1), "current": round(current_total, 1), "matched": matched}


VERDICT_LABELS = {
    "worked_out": "This trade has worked out",
    "didnt_pan_out": "This trade hasn't paid off yet",
    "mixed": "Mixed results so far",
    "neutral": "Roughly even so far",
}


def _combine_directions(
    *, production_direction: int | None, value_direction: int | None
) -> tuple[str, str]:
    """Combine whichever signals exist into (verdict_key, confidence).
    Conflicting non-zero directions read as "mixed" rather than picking a
    side; agreement across both available signals is the only "high"
    confidence path."""

    directions = [d for d in (production_direction, value_direction) if d is not None]
    if not directions:
        return "neutral", "low"
    nonzero = [d for d in directions if d != 0]
    if not nonzero:
        return "neutral", "medium" if len(directions) == 2 else "low"
    if 1 in nonzero and -1 in nonzero:
        return "mixed", "low"
    direction = nonzero[0]
    confidence = "high" if len(directions) == 2 and len(nonzero) == 2 else "medium" if len(directions) == 2 else "low"
    return ("worked_out" if direction > 0 else "didnt_pan_out"), confidence


def compute_trade_result(
    *,
    trade_summary: Mapping[str, Any],
    outcome_recorded_at: str | None,
    current_value_by_player: Mapping[str, float],
    season_stats: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Pure computation (no network I/O) — everything provider-facing is
    resolved by the caller first, so this is exhaustively unit-testable
    without ever touching modules.rankings or modules.sleeper directly."""

    now = now or datetime.now(timezone.utc)
    days_since_trade: int | None = None
    if outcome_recorded_at:
        try:
            recorded = datetime.fromisoformat(str(outcome_recorded_at).replace("Z", "+00:00"))
            if recorded.tzinfo is None:
                recorded = recorded.replace(tzinfo=timezone.utc)
            days_since_trade = max(0, (now - recorded).days)
        except Exception:
            days_since_trade = None

    send_assets = _asset_list(trade_summary, "send")
    receive_assets = _asset_list(trade_summary, "receive")
    tracked_send = _tracked_assets(send_assets)
    tracked_receive = _tracked_assets(receive_assets)

    base: dict[str, Any] = {
        "days_since_trade": days_since_trade,
        "tracked_send_count": len(tracked_send),
        "tracked_receive_count": len(tracked_receive),
        "total_send_count": len(send_assets),
        "total_receive_count": len(receive_assets),
    }

    if not tracked_send and not tracked_receive:
        return {**base, "status": "insufficient_data", "reason": "no_tracked_players", "verdict": None}

    weeks_elapsed = weeks_elapsed_for(days_since_trade)
    send_production = _side_production(send_assets, season_stats, weeks_elapsed)
    receive_production = _side_production(receive_assets, season_stats, weeks_elapsed)
    send_value = _side_value(send_assets, current_value_by_player)
    receive_value = _side_value(receive_assets, current_value_by_player)

    production_signal: dict[str, Any] | None = None
    if send_production["has_data"] or receive_production["has_data"]:
        weeks_for_avg = max(send_production["weeks_counted"], receive_production["weeks_counted"], 1)
        net_points = receive_production["points_ppr"] - send_production["points_ppr"]
        production_signal = {
            "net_points_ppr": round(net_points, 1),
            "avg_net_per_week": round(net_points / weeks_for_avg, 2),
            "weeks_counted": weeks_for_avg,
        }

    value_signal: dict[str, Any] | None = None
    if send_value["matched"] and receive_value["matched"] and send_value["baseline"] and receive_value["baseline"]:
        sent_delta_pct = (send_value["current"] - send_value["baseline"]) / send_value["baseline"] * 100
        received_delta_pct = (receive_value["current"] - receive_value["baseline"]) / receive_value["baseline"] * 100
        value_signal = {
            "sent_delta_pct": round(sent_delta_pct, 1),
            "received_delta_pct": round(received_delta_pct, 1),
            "net_delta_pct": round(received_delta_pct - sent_delta_pct, 1),
        }

    if production_signal is None and value_signal is None:
        return {
            **base,
            "status": "insufficient_data",
            "reason": "no_stat_data_yet",
            "verdict": None,
            "send": {"production": send_production, "value": send_value},
            "receive": {"production": receive_production, "value": receive_value},
        }

    production_direction = None
    if production_signal is not None:
        avg = production_signal["avg_net_per_week"]
        production_direction = 1 if avg >= PRODUCTION_THRESHOLD_PER_WEEK else -1 if avg <= -PRODUCTION_THRESHOLD_PER_WEEK else 0

    value_direction = None
    if value_signal is not None:
        net = value_signal["net_delta_pct"]
        value_direction = 1 if net >= VALUE_DELTA_THRESHOLD_PCT else -1 if net <= -VALUE_DELTA_THRESHOLD_PCT else 0

    verdict_key, confidence = _combine_directions(production_direction=production_direction, value_direction=value_direction)

    return {
        **base,
        "status": "ready",
        "reason": "",
        "verdict": verdict_key,
        "verdict_label": VERDICT_LABELS[verdict_key],
        "confidence": confidence,
        "production": production_signal,
        "value": value_signal,
        "send": {"production": send_production, "value": send_value},
        "receive": {"production": receive_production, "value": receive_value},
    }


def load_valued_players_for_result(lens: str, league_settings: Mapping[str, Any] | None) -> tuple[pd.DataFrame, str]:
    """Same cache-first/build-fallback shape as
    modules.push_triggers.load_valued_players — kept as its own copy (not
    imported) so this standalone cron job never depends on the push-trigger
    sweep module. NEVER call rankings.load_players/build_players_table
    against anything but this real production path from a test — tests must
    monkeypatch this function or the two rankings calls it wraps."""

    players_df = rankings.load_players(PLAYERS_DB_PATH)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(PLAYERS_DB_PATH)
    players_df = player_eligibility.filter_current_fantasy_players(players_df, surface="trade_outcome_result_sweep")
    if players_df.empty:
        return players_df, ""
    valued = league_value_settings.apply_valuation_lens(players_df, lens, league_settings)
    score_field = league_value_settings.valuation_score_field(lens)
    return valued, score_field


def _current_value_by_player(valued_df: pd.DataFrame, score_field: str) -> dict[str, float]:
    if valued_df is None or valued_df.empty or not score_field or score_field not in valued_df.columns:
        return {}
    ids = valued_df["player_id"].astype(str) if "player_id" in valued_df.columns else None
    if ids is None:
        return {}
    scores = pd.to_numeric(valued_df[score_field], errors="coerce")
    return {pid: float(score) for pid, score in zip(ids, scores) if score == score}  # drop NaN


def run_trade_outcome_result_sweep(*, environ: dict | None = None, secrets: Any = None) -> dict[str, Any]:
    """One sweep of the quiet "did it work?" result computation. Never
    raises — a bad row is logged into `errors` and skipped. Sends no push,
    shows no popup: purely writes result_summary/result_computed_at for the
    mobile Trade History screen (GET /v1/trade-outcomes/history) to read on
    its own next pull."""

    config = load_result_sweep_config(environ=environ, secrets=secrets)
    stats: dict[str, Any] = {
        "ok": True,
        "configured": config.configured,
        "outcomes_checked": 0,
        "results_computed": 0,
        "errors": [],
    }
    if not config.configured:
        stats["ok"] = False
        stats["errors"].append("Supabase service-role is not configured.")
        return stats

    pending = fetch_pending_trade_outcome_results(config)
    if not pending:
        return stats

    season_stats: Mapping[str, Any] | None = None
    valued_cache: dict[tuple[str, str], tuple[pd.DataFrame, str]] = {}

    for row in pending:
        stats["outcomes_checked"] += 1
        outcome_id = _safe_text(row.get("id"))
        if not outcome_id:
            continue
        trade_summary = row.get("trade_summary") if isinstance(row.get("trade_summary"), Mapping) else {}
        try:
            tracked = _tracked_assets(_asset_list(trade_summary, "send")) or _tracked_assets(
                _asset_list(trade_summary, "receive")
            )
            if not tracked:
                store_trade_outcome_result(
                    config,
                    outcome_id=outcome_id,
                    result_summary={"status": "insufficient_data", "reason": "no_tracked_players", "verdict": None},
                )
                stats["results_computed"] += 1
                continue

            if season_stats is None:
                season_stats = sleeper.get_season_player_stats(retain_weekly=True) or {}

            league_id = _safe_text(row.get("league_id"))
            lens = _safe_text(trade_summary.get("valuation_lens")) or DEFAULT_LENS
            cache_key = (league_id, lens)
            if cache_key not in valued_cache:
                league_settings: dict[str, Any] = {}
                try:
                    league = sleeper.get_league(league_id) if league_id else None
                    if league:
                        league_settings = league_value_settings.detect_league_value_settings_from_payload(league)
                except Exception:
                    league_settings = {}
                valued_cache[cache_key] = load_valued_players_for_result(lens, league_settings)
            valued_df, score_field = valued_cache[cache_key]
            current_value_by_player = _current_value_by_player(valued_df, score_field)

            result_summary = compute_trade_result(
                trade_summary=trade_summary,
                outcome_recorded_at=row.get("outcome_recorded_at"),
                current_value_by_player=current_value_by_player,
                season_stats=season_stats,
            )
            store_trade_outcome_result(config, outcome_id=outcome_id, result_summary=result_summary)
            stats["results_computed"] += 1
        except Exception as exc:
            stats["errors"].append(f"{outcome_id}: {exc}")

    return stats
