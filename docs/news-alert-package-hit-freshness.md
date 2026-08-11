# News alert package-HIT freshness

Base / rollback: `1009dad1642094e32811d7e2aca5e8a2637caf7b` (main @ #260)

## Verdict

**NEWS ALERT PACKAGE-HIT FRESHNESS TRUSTWORTHY**

## Root cause

News Alert tiles were built only on Game Plan package MISS and frozen inside
`dashboard_briefing`. Package fingerprint is football-only, so a HIT restored
stale alerts while the news disk cache could advance independently.

## Boundary

| Layer | Owner | Invalidated by |
|---|---|---|
| Football package | `game_plan_package` | lifecycle/roster/settings fingerprint |
| Ephemeral news alerts | `news_intelligence.refresh_news_alerts_for_presentation` | `presentation_digest_from_tiles` |
| News disk pool | `news.load_cached_news_pool` | existing TTL refresh (not Dashboard) |

On package HIT, Dashboard refreshes News Alert tiles + notification inventory
from cached articles without rebuilding football evaluation.

## Digest schema

SHA-256/32 over sorted alert rows:
`recommendation_id|event_type|player_id|confidence|severity|relationship|confirmation|title`

No raw article prose.

## Invariants

1. Fresh important cached article → alert refresh; football package remains HIT
2. Article alone does **not** rebuild football evaluation
3. Valuation still changes only via structured Sleeper/status truth
4. Duplicate/syndicated articles share identity → one tile
5. League/account switch clears presentation digest via package clear
6. Package HIT path: 0 live RSS calls (`load_cached_news_pool` only)
