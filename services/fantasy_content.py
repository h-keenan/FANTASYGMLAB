"""Read-only public-audience content export; separate from user/league sessions."""
from __future__ import annotations
import hashlib
import hmac
import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException
from modules import player_value_history, rankings, player_eligibility, player_quick_view, sleeper
from modules.public_roster_percentages import roster_percentages


def require_content_token(authorization: str | None = Header(default=None)):
    expected = os.environ.get("FGL_CONTENT_TOKEN_SHA256", "").strip().lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise HTTPException(503, "Content export credential is not configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or len(token) < 32 or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), expected):
        raise HTTPException(401, "Content export credential required")


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def roster_population(now):
    path = os.environ.get("FGL_CONTENT_ROSTERED_FILE", "")
    if not path:
        return {}
    file = Path(path)
    if not file.is_file() or file.stat().st_size > 2_000_000:
        return {}
    try:
        payload = json.loads(file.read_text())
        result = {}
        for row in payload.get("players", [])[:10000]:
            stamp = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
            value = number(row["percent"])
            if stamp.tzinfo is None or not -60 <= now - stamp.timestamp() <= 86400 or value is None or not 0 <= value <= 100:
                continue
            if not row.get("platform") or not row.get("league_format") or not str(row.get("source_url", "")).startswith("https://"):
                continue
            result[str(row["player_id"])] = {k: row[k] for k in ("percent", "platform", "league_format", "source_url", "observed_at")}
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def build_feed(db_path, news_loader):
    frame = rankings.load_players(db_path)
    if frame is None or frame.empty:
        raise HTTPException(503, "Player data is unavailable")
    frame = player_eligibility.filter_current_fantasy_players(frame, surface="content_export")
    frame = frame[frame["position"].isin(["QB", "RB", "WR", "TE"])].copy()
    score = "dynasty_score" if "dynasty_score" in frame.columns else "score"
    frame["content_ovr"] = player_quick_view.overall_ratings_for_pool(frame, score_column=score)
    now = time.time()
    source_at = Path(db_path).stat().st_mtime
    if source_at > now + 60 or now - source_at > 86400:
        raise HTTPException(503, "Player values require a source refresh")
    players = []
    for _, row in frame.iterrows():
        value = number(row.get(score))
        pid = str(row.get("player_id") or "")
        if value is None or value < 0 or not pid.isdigit():
            continue
        players.append({"player_id": pid, "name": str(row.get("name") or ""),
                        "team": str(row.get("team") or ""), "position": str(row["position"]),
                        "value_score": value, "overall_rating": number(row.get("content_ovr")), "active": True})
    if not players:
        raise HTTPException(503, "No current player values available")
    players.sort(key=lambda row: (-row["value_score"], row["player_id"]))
    by_id = {row["player_id"]: row for row in players}
    stamp = datetime.fromtimestamp(now, timezone.utc).isoformat()
    ideas = []
    rostered = roster_percentages(frame, now)
    rostered.update(roster_population(now))
    try:
        trends = sleeper.trending_add_rank_map(lookback_hours=24, limit=30)
    except Exception:
        trends = {}
    for pid, trend in sorted(trends.items(), key=lambda pair: pair[1].get("rank", 999)):
        player = by_id.get(str(pid))
        count = trend.get("count")
        if not player or not isinstance(count, int) or count <= 0 or (str(pid) in rostered and rostered[str(pid)]["percent"] > 70):
            continue
        ideas.append({"player_id": str(pid), "name": player["name"], "team": player["team"],
                      "position": player["position"],
                      "reason": f"Sleeper recorded {count} adds in the last 24h. Review his role and league availability.",
                      "source_name": "FantasyGM Lab / Sleeper trending adds",
                      "source_url": "https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=30",
                      "observed_at": stamp, "rostered": rostered.get(str(pid)), "overall_rating": player["overall_rating"]})
    try:
        news = news_loader()
    except Exception:
        news = []
    # Explicit allowlist: no account, roster, league, billing, or session data is exported.
    news = [{k: item.get(k) for k in ("title", "link", "source", "summary", "published_ts", "event_type", "speculative")} for item in news[:20]]

    # Overall-score deltas + a structured "why" since the last players.db
    # refresh (see modules.player_value_history). Gated on the same source
    # fingerprint the public hydration pipeline already uses, so repeated
    # feed reads between refreshes return the same cached diff.
    try:
        raw_changes = player_value_history.value_changes_since_last_refresh(db_path, frame, limit=40)
    except Exception:
        raw_changes = []
    value_changes = []
    for change in raw_changes:
        player = by_id.get(str(change.get("player_id")))
        if not player:
            continue
        value_changes.append({**change, "name": player["name"], "team": player["team"],
                              "position": player["position"], "overall_rating": player["overall_rating"]})

    # Sleeper global add-velocity over the trailing week (168h), distinct from
    # the 24h "ideas" list above — raw counts for any trending player, not a
    # curated/roster%-filtered top-8. Reuses sleeper.trending_add_rank_map's
    # existing cached call (see modules/sleeper.py's TRENDING_ENDPOINT_TTL_SECONDS),
    # so this never adds a second uncached hot path to Sleeper.
    try:
        week_trends = sleeper.trending_add_rank_map(lookback_hours=24 * 7, limit=100)
    except Exception:
        week_trends = {}
    trending_adds_week = []
    for pid, trend in sorted(week_trends.items(), key=lambda pair: pair[1].get("rank", 999)):
        player = by_id.get(str(pid))
        count = trend.get("count")
        if not player or not isinstance(count, int) or count <= 0:
            continue
        trending_adds_week.append({"player_id": str(pid), "name": player["name"], "team": player["team"],
                                   "position": player["position"], "add_count": count,
                                   "rank": trend.get("rank"), "lookback_hours": 24 * 7})

    return {"schema_version": 1, "generated_at": now,
            "rankings": {"schema_version": 1, "source_id": "FantasyGM Lab API", "format_id": "base-dynasty",
                         "model_version": str(rankings.VALUATION_AUTHORITY_CONTRACT_VERSION),
                         "source_at": source_at, "generated_at": now, "players": players},
            "waiver_watch": ideas[:8], "news": news,
            "value_changes": value_changes,
            "trending_adds_week": trending_adds_week,
            "roster_percentage_status": "available" if any(i["rostered"] for i in ideas) else "unavailable", "audience": "general-public"}


def content_reader(db_path, refresh_players, news_loader):
    lock = threading.Lock()
    cache = {"expires": 0, "feed": None}
    def feed():
        refresh_players()
        with lock:
            if time.time() >= cache["expires"]:
                cache["feed"] = build_feed(db_path, news_loader)
                cache["expires"] = time.time() + 300
            return cache["feed"]
    return feed


def content_router(db_path, refresh_players, news_loader):
    router = APIRouter(prefix="/v1/content", dependencies=[Depends(require_content_token)])
    router.add_api_route("/feed", content_reader(db_path, refresh_players, news_loader), methods=["GET"])
    return router
