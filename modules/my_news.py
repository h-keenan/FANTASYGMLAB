import html
import re
import time
from typing import List, Dict, Any, Optional

from modules import runtime_trace
TEAM_NAME_ALIASES = {
    "ARI": ["Arizona", "Cardinals"],
    "ATL": ["Atlanta", "Falcons"],
    "BAL": ["Baltimore", "Ravens"],
    "BUF": ["Buffalo", "Bills"],
    "CAR": ["Carolina", "Panthers"],
    "CHI": ["Chicago", "Bears"],
    "CIN": ["Cincinnati", "Bengals"],
    "CLE": ["Cleveland", "Browns"],
    "DAL": ["Dallas", "Cowboys"],
    "DEN": ["Denver", "Broncos"],
    "DET": ["Detroit", "Lions"],
    "GB": ["Green Bay", "Packers"],
    "HOU": ["Houston", "Texans"],
    "IND": ["Indianapolis", "Colts"],
    "JAX": ["Jacksonville", "Jaguars"],
    "KC": ["Kansas City", "Chiefs"],
    "LAC": ["Los Angeles", "Chargers"],
    "LAR": ["Los Angeles", "Rams"],
    "LV": ["Las Vegas", "Raiders"],
    "MIA": ["Miami", "Dolphins"],
    "MIN": ["Minnesota", "Vikings"],
    "NE": ["New England", "Patriots"],
    "NO": ["New Orleans", "Saints"],
    "NYG": ["New York", "Giants"],
    "NYJ": ["New York", "Jets"],
    "PHI": ["Philadelphia", "Eagles"],
    "PIT": ["Pittsburgh", "Steelers"],
    "SEA": ["Seattle", "Seahawks"],
    "SF": ["San Francisco", "49ers", "Niners"],
    "TB": ["Tampa Bay", "Buccaneers"],
    "TEN": ["Tennessee", "Titans"],
    "WAS": ["Washington", "Commanders"],
}


def _slugify_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return normalized


def _team_terms_for_roster(team_codes: List[str]) -> List[str]:
    terms = []
    for code in team_codes:
        code = str(code).upper().strip()
        if not code:
            continue
        if code not in terms:
            terms.append(code.lower())
        aliases = TEAM_NAME_ALIASES.get(code)
        if aliases:
            for alias in aliases:
                term = alias.lower()
                if term not in terms:
                    terms.append(term)
    return terms


NEWS_CONTEXTS = {
    "injury/status": [
        "injury",
        "injured",
        "questionable",
        "probable",
        "doubtful",
        "unlikely",
        "out",
        "inactive",
        "practice",
        "limited",
        "full participant",
        "did not practice",
        "surgery",
        "injured reserve",
        "ir",
        "pup",
        "nfi",
        "protocol",
        "concussion",
        "hamstring",
        "ankle",
        "knee",
        "illness",
        "return",
        "activated",
        "designated to return",
    ],
    "role/depth chart": [
        "starter",
        "starting",
        "depth chart",
        "first-team",
        "first team",
        "backup",
        "benched",
        "qb1",
        "rb1",
        "wr1",
        "te1",
        "competition",
        "compete",
        "snap",
        "snaps",
        "target",
        "targets",
        "workload",
        "touches",
    ],
    "transaction": [
        "signed",
        "released",
        "waived",
        "claimed",
        "elevated",
        "practice squad",
        "extension",
        "contract",
        "trade",
        "traded",
        "acquired",
    ],
    "off-field/drama": [
        "holdout",
        "hold-in",
        "unhappy",
        "trade request",
        "suspended",
        "suspension",
        "arrest",
        "charged",
        "domestic",
        "lawsuit",
        "discipline",
        "fine",
        "investigation",
    ],
}
NEWS_PRIORITY_WEIGHTS = {
    "injury/status": 36,
    "transaction": 30,
    "role/depth chart": 26,
    "off-field/drama": 22,
}


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase = phrase.lower().strip()
    if not phrase:
        return False
    if " " in phrase or "-" in phrase:
        return phrase in text
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _context_matches(text: str) -> List[str]:
    matches = []
    for label, phrases in NEWS_CONTEXTS.items():
        if any(_contains_phrase(text, phrase) for phrase in phrases):
            matches.append(label)
    return matches


def news_timestamp(item: Dict[str, Any]) -> float:
    ts = item.get("published_ts")
    if ts:
        try:
            return float(ts)
        except Exception:
            pass
    parsed = item.get("published_parsed")
    if parsed:
        try:
            return time.mktime(parsed)
        except Exception:
            return 0.0
    return 0.0


def news_priority_score(item: Dict[str, Any]) -> int:
    base = int(item.get("relevance_score") or 0)
    reason = str(item.get("relevance_reason") or "").lower()
    for label, weight in NEWS_PRIORITY_WEIGHTS.items():
        if label in reason:
            base += weight

    ts = news_timestamp(item)
    if ts > 0:
        age_seconds = max(0.0, time.time() - ts)
        if age_seconds <= 6 * 60 * 60:
            base += 24
        elif age_seconds <= 24 * 60 * 60:
            base += 18
        elif age_seconds <= 3 * 24 * 60 * 60:
            base += 11
        elif age_seconds <= 7 * 24 * 60 * 60:
            base += 5
    return base


def relative_news_time(item: Dict[str, Any]) -> str:
    ts = news_timestamp(item)
    if ts <= 0:
        return ""
    delta = max(0, int(time.time() - ts))
    if delta < 60:
        return "just now"
    if delta < 60 * 60:
        minutes = max(1, delta // 60)
        return f"{minutes}m ago"
    if delta < 24 * 60 * 60:
        hours = max(1, delta // (60 * 60))
        return f"{hours}h ago"
    if delta < 7 * 24 * 60 * 60:
        days = max(1, delta // (24 * 60 * 60))
        return f"{days}d ago"
    return time.strftime("%b %d", time.localtime(ts))


def _player_terms(player_names: List[str]) -> List[Dict[str, str]]:
    players = []
    for full in player_names:
        if not isinstance(full, str):
            continue
        name = full.strip()
        if not name:
            continue
        lower_name = name.lower()
        parts = lower_name.split()
        last_name = parts[-1] if len(parts) > 1 else lower_name
        if len(last_name) < 4:
            last_name = ""
        players.append({"name": name, "full": lower_name, "last": last_name})
    return players


def _plain_news_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\bwww\.\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -|•\t\r\n")
    return text


def _normalize_news_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _plain_news_text(value).lower())


def build_quick_news_summary(item: Dict[str, Any], max_chars: int = 220) -> str:
    """
    Return a clean, short summary for display.
    RSS feeds, especially Google News, often put source links in summary fields.
    """
    title = _plain_news_text(item.get("title"))
    link = str(item.get("link") or "")
    candidates = [
        item.get("summary"),
        item.get("description"),
        item.get("content"),
        item.get("body"),
    ]

    title_norm = _normalize_news_text(title)
    link_norm = _normalize_news_text(link)
    source = _plain_news_text(item.get("source"))
    source_norm = _normalize_news_text(source)

    for candidate in candidates:
        raw_candidate = str(candidate or "")
        looks_like_feed_markup = bool(re.search(r"<\s*(a|font)\b|&nbsp;", raw_candidate, flags=re.IGNORECASE))
        text = _plain_news_text(candidate)
        if not text:
            continue

        text = re.sub(r"\b(Read full article|Full article|View full coverage|More from|Continue reading)\b.*$", "", text, flags=re.IGNORECASE).strip()
        if title and text.lower().startswith(title.lower()):
            text = text[len(title):].strip(" -|:•")

        text_norm = _normalize_news_text(text)
        if not text_norm:
            continue
        if text_norm in {title_norm, link_norm, source_norm}:
            continue
        if title_norm and (text_norm == title_norm or text_norm in title_norm):
            continue
        if len(text) < 24 and source_norm and source_norm in text_norm:
            continue
        if looks_like_feed_markup and len(text) < 40:
            continue

        if len(text) > max_chars:
            cutoff = text[: max_chars + 1].rsplit(" ", 1)[0].rstrip(".,;:")
            text = f"{cutoff}..."
        return text

    matched_player = _plain_news_text(item.get("matched_player"))
    reason = _plain_news_text(item.get("relevance_reason"))
    if reason and reason != "player mention":
        context = reason.replace("/", " or ")
        if matched_player:
            return f"Quick read: {matched_player} is tied to {context} news. Open the headline for the full report."
        return f"Quick read: roster-relevant {context} news. Open the headline for the full report."
    if matched_player:
        return f"Quick read: {matched_player} was mentioned in a roster-relevant NFL update. Open the headline for details."
    if title:
        return "Quick read: roster-relevant NFL headline. Open the headline for details."
    return ""


@runtime_trace.traced(
    "curate_player_news",
    phase="news_retrieval",
    counter="news_parsing",
)
def curate_player_news(items: List[Dict[str, Any]], max_items: int = 12) -> List[Dict[str, Any]]:
    """
    Keep the news feed focused on current roster-impacting items.
    Prefer injury, trade, and role/status updates over stale player mentions.
    """
    if not items:
        return []

    prioritized: List[Dict[str, Any]] = []
    priority_players = set()
    for raw_item in items:
        item = dict(raw_item)
        item["priority_score"] = int(item.get("priority_score") or news_priority_score(item))
        item["published_ts"] = news_timestamp(item)
        reason = _plain_news_text(item.get("relevance_reason")).strip().lower()
        player_key = _plain_news_text(item.get("matched_player")).strip().casefold()
        age_seconds = 0.0
        if item["published_ts"] > 0:
            age_seconds = max(0.0, time.time() - float(item["published_ts"]))
        item["_reason_key"] = reason
        item["_player_key"] = player_key
        item["_age_seconds"] = age_seconds
        item["_priority_reason"] = reason not in {"", "player mention"}
        if item["_priority_reason"] and player_key:
            priority_players.add(player_key)
        prioritized.append(item)

    prioritized.sort(
        key=lambda item: (
            int(item.get("priority_score") or 0),
            float(item.get("published_ts") or 0),
        ),
        reverse=True,
    )

    curated: List[Dict[str, Any]] = []
    seen_links = set()
    player_counts: Dict[str, int] = {}
    for item in prioritized:
        link_key = str(item.get("link") or "").strip().lower()
        if link_key and link_key in seen_links:
            continue

        player_key = str(item.get("_player_key") or "")
        reason = str(item.get("_reason_key") or "")
        age_seconds = float(item.get("_age_seconds") or 0.0)
        is_priority_reason = bool(item.get("_priority_reason"))

        if not is_priority_reason and player_key in priority_players:
            continue
        if reason == "player mention" and age_seconds > 48 * 60 * 60:
            continue
        if not is_priority_reason and age_seconds > 7 * 24 * 60 * 60:
            continue
        if player_key and player_counts.get(player_key, 0) >= 2:
            continue

        if link_key:
            seen_links.add(link_key)
        if player_key:
            player_counts[player_key] = player_counts.get(player_key, 0) + 1

        item.pop("_reason_key", None)
        item.pop("_player_key", None)
        item.pop("_age_seconds", None)
        item.pop("_priority_reason", None)
        curated.append(item)
        if len(curated) >= max_items:
            break

    return curated


@runtime_trace.traced(
    "filter_news_for_players",
    phase="news_retrieval",
    counter="news_parsing",
)
def filter_news_for_players(
    news_items: List[Dict], player_names: List[str], roster_teams: Optional[List[str]] = None
) -> List[Dict]:
    """
    Filter news to items that are relevant to roster players.
    """
    if not news_items or not player_names:
        return []

    player_terms = _player_terms(player_names)
    team_terms = _team_terms_for_roster(roster_teams or [])

    filtered: List[Dict] = []
    seen_links = set()
    for item in news_items:
        link = str(item.get("link", "") or "").lower()
        text = " ".join(
            str(item.get(key, "") or "")
            for key in ["title", "summary", "description", "body", "content"]
        ).lower()

        contexts = _context_matches(text)
        team_match = any(_contains_phrase(text, term) for term in team_terms)
        matched_player = ""
        relevance_reason = ""
        relevance_score = 0

        for player in player_terms:
            if _contains_phrase(text, player["full"]):
                matched_player = player["name"]
                relevance_score = 100 + (20 if contexts else 0)
                relevance_reason = ", ".join(contexts) if contexts else "player mention"
                break
            if player["last"] and _contains_phrase(text, player["last"]) and contexts:
                matched_player = player["name"]
                relevance_score = 70 + (10 if team_match else 0)
                relevance_reason = ", ".join(contexts)
                break

        if matched_player and link and link not in seen_links:
            seen_links.add(link)
            item = dict(item)
            item["matched_player"] = matched_player
            item["relevance_reason"] = relevance_reason
            item["relevance_score"] = relevance_score
            item["priority_score"] = news_priority_score(item)
            filtered.append(item)

    filtered.sort(
        key=lambda item: (
            int(item.get("priority_score") or news_priority_score(item)),
            news_timestamp(item),
        ),
        reverse=True,
    )
    return filtered


def build_sleeper_roster_updates(df_team, max_items: int = 12) -> List[Dict[str, Any]]:
    """
    Build automatic roster-specific update cards from Sleeper player metadata.
    This keeps the News tab useful even when external RSS feeds are unavailable.
    """
    if df_team is None or df_team.empty or "news_updated" not in df_team.columns:
        return []

    updates: List[Dict[str, Any]] = []
    for _, row in df_team.iterrows():
        news_updated = row.get("news_updated")
        try:
            timestamp = float(news_updated)
        except Exception:
            continue

        if timestamp <= 0:
            continue
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0

        name = str(row.get("name") or "Player").strip()
        team = str(row.get("team") or "").strip()
        status = str(row.get("status") or "").strip()
        depth = str(row.get("depth_chart_position") or "").strip()
        player_id = str(row.get("player_id") or "").strip()

        details = []
        if team:
            details.append(f"Team: {team}")
        if status:
            details.append(f"Status: {status}")
        if depth:
            details.append(f"Depth chart: {depth}")

        updated_at = time.strftime("%b %d, %Y", time.localtime(timestamp))
        summary = " | ".join(details) if details else "Sleeper player profile changed."
        summary = f"{summary} | Updated {updated_at}"

        updates.append(
            {
                "title": f"{name} roster update",
                "summary": summary,
                "description": summary,
                "content": summary,
                "body": "",
                "link": f"https://sleeper.com/players/nfl/{player_id}" if player_id else "",
                "published": updated_at,
                "published_ts": timestamp,
                "source": "Sleeper",
                "is_sleeper_update": True,
                "matched_player": name,
                "relevance_reason": "Sleeper status/role metadata changed",
                "relevance_score": 90,
            }
        )

    updates.sort(key=lambda item: float(item.get("published_ts") or 0), reverse=True)
    return updates[:max_items]
