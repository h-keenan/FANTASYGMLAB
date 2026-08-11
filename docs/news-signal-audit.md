# News → signal → alert → evaluation audit

Branch: `cursor/news-signal-audit-71e1`  
Rollback SHA: `fb4ab7dfdf09f58279d41acf478195b401f12da5` (main @ #248)

## Verdict

**NEWS SIGNAL SYSTEM NEEDS MORE WORK** for a full closed-loop
alert→evaluation product (alerts still do not originate from articles;
roster-aware article alerts and dynasty/redraft article impact remain debt).

**Proven this pass:** article text does **not** mutate canonical value;
classification/confidence/entity/stale bugs that *were* distorting news ranking
are fixed; false/true-positive harnesses lock the separation.

---

## 1. Current architecture (end-to-end)

```
provider/article
  Rotowire / ESPN / CBS RSS  →  modules/news.fetch_news
  Google News per-player     →  modules/news.fetch_roster_news
  Sleeper player meta        →  modules/my_news.build_sleeper_roster_updates
        ↓
normalize (_entry_to_item / plain text)
        ↓
entity match (full name / last+context+team; suffix-normalized)
        ↓
event classification (modules/news_signal.classify_article)
        ↓
confidence + source_quality + speculative flag
        ↓
ranking-only priority_adjustment  ✗ never writes score/dynasty_score/value_score
        ↓
curate (link + event_identity dedupe, stale gates)
        ↓
UI: News page / PQV Recent News / sidebar (session)
alerts: Notification Center ← Dashboard tiles (Sleeper injury / trade / waiver)
evaluation: risk_multiplier ← Sleeper status + injury_status only
```

### Providers / sources
| Source | Module | Notes |
|---|---|---|
| Rotowire / ESPN / CBS RSS | `news.NEWS_FEEDS` | League pool |
| Google News RSS | `fetch_roster_news` | Per-player fan-out ≤28 |
| Sleeper metadata | `build_sleeper_roster_updates` | Synthetic cards from `news_updated` |

### Cache behavior
| Layer | TTL |
|---|---|
| `data/news_cache.json` | **20m fresh short-circuit** (added this PR); fallback forever |
| `data/roster_news_cache.json` | 20m |
| Session `news` / roster keys | 900s gate on News page |
| PQV presentation cache | 20m |
| Dashboard cold path | **0 RSS calls** |

### Entity matching
- Full-name phrase match (suffix-normalized Jr/Sr/II/III)
- Last-name (≥4) + context keywords + optional team alias
- **Blocked** when surname collides across roster without full name

### Event taxonomy
`injury/status`, `role/depth chart`, `transaction`, `off-field/drama`,
`player mention` / `player headline`, Sleeper meta label.
Legacy Google alias: `transaction/drama`.

### Confidence taxonomy
`official_confirmed` → `strong_reporter_confirmation` → `coach_statement` →
`credible_observation` → `speculation`

### Source quality (coarse — not a giant rating framework)
`official`, `major_national`, `beat_or_wire`, `aggregator`, `opinion_fantasy`, `unknown`

### Structured fields news may write (article dict only)
`relevance_*`, `priority_score`, `matched_player`, `signal_*`, `event_identity`  
**Not written:** `score`, `dynasty_score`, `value_score`, `news_factor` (always 0),
`injury_status`, `status`, depth chart columns.

### Direct evaluation dependency on news articles
**None.** Deleted `modules/news_factor.py`; rankings force `news_factor = 0.0`.

Evaluation still consumes **Sleeper** `status` / `injury_status` via
`injury_level` → `risk_multiplier` / `current_availability_multiplier`.

---

## 2. News must not equal value

| Path | Affects value? |
|---|---|
| RSS / Google headline text | **No** |
| Sentiment / speculative prose | **No** (ranking penalty only) |
| Sleeper IR / Out / Questionable | **Yes** (risk multipliers) |
| `news_updated` freshness | Team injury-impact display / eligibility corroboration only |

---

## 3–5. Injury / role / source behavior

- Injury **alerts** on Dashboard come from Sleeper status tiles, not articles.
- Role/position-battle language is classified with confidence tiers; speculation
  is down-ranked (−40 priority) and expires faster in curation (3d).
- Official depth-chart / named-starter language ranks above “may start / could see more work”.
- Source quality is reported on items; material evaluation still requires
  structured provider status (Sleeper), not headline alone.

---

## 6–7. Entity + stale / duplicate

- Surname collision fixture: “Thomas questionable” with Michael+Logan Thomas → no match.
- `Kenneth Walker III` IR headline matches with suffix normalization.
- `event_identity` dedupes syndicated same-day copies with different URLs.
- Speculative items older than 3 days dropped in `curate_player_news`.

---

## 8–9. Alerts + roster-aware importance

**Current:** alerts = Dashboard recommendation tiles (trades/waivers/injuries),
deduped by recommendation signature, not by article event_identity.

**Debt:** articles do not emit Notification Center items; roster-aware urgency
(my starter vs FA vs other roster) is **not** applied to headlines—only to
League Intelligence ownership labels on the News page.

---

## 10–12. Evaluation / mode / PPR

| Event type | Immediate valuation | Risk | Opportunity | Recs | Alert |
|---|---|---|---|---|---|
| Speculative headline | none | none | none | ranking only | none |
| Confirmed article (no status change) | none | none | none | ranking only | none |
| Sleeper major IR / torn ACL status | yes | yes | availability | Game Plan injury tile | Injury Alert |
| Sleeper minor Q | mild | mild | availability | possible | possible |
| Depth chart via Sleeper fields | role_score path | — | opportunity profile | — | — |

Dynasty vs redraft divergence is in **status multipliers**
(`risk_multiplier` vs harsher `current_availability_multiplier`), not articles.
PPR/scoring multipliers do not read news.

---

## 13–14. Harnesses

`tests/test_news_signal_audit.py`
- False positives: clickbait / speculation / fantasy opinion → speculative;
  scores unchanged; substring traps fixed.
- True positives: Sleeper IR/ACL lowers risk; official starter > speculative role;
  entity collision blocked; stale speculative curated out; fetch TTL short-circuit.

---

## 15. Performance

| Metric | Before | After |
|---|---|---|
| `fetch_news` on warm disk | always 3 live RSS | **0** when cache &lt; 20m |
| Dashboard cold RSS | 0 | 0 |
| Classification | keyword bags | shared `news_signal` (in-process, no I/O) |

---

## Bugs discovered → fixed

1. Substring `"out"`/`"ir"`/`"role"` false classifications in `news._player_news_reason`
2. Incomplete `NEWS_REASON_LABELS` for transaction / off-field / headline
3. `fetch_news` ignored disk TTL (startup/news-page tax)
4. No confidence tier → speculative role news ranked like confirmation
5. Ambiguous surname matching could attach wrong player
6. Syndicated duplicates only deduped by URL
7. Zero news unit tests

## Remaining debt

- Article-originated alerts with roster-aware severity/expiration
- Corroboration gate before any future structured football-state mutation
- Populate dead `role_change_note` / `depth_chart_note` from Sleeper diffs (not headlines)
- Richer source-reliability model (intentionally deferred)
- Dynasty vs redraft *article* impact (should stay none until structured facts exist)
- Remove misleading debug “News factor” displays (always 0)

## Validation

- Focused news harness: pass
- Full pytest / compileall / diff-check / perf budget: recorded in PR
