# Plan: hosted leagues and college football

Status: research and plan only. No app code. Written 2026-11-01.
Origin (coridian_): "we need to start thinking about hosting fantasy and
implementing college in some way. Because having 130+ teams isn't fair but we
could do survivor league or something or limit it to conference."

Honesty note: web findings below came from search snippets and a few page
fetches. Anything about pricing, platform policy, or law may have changed and
must be re-verified before a decision. Nothing here is a legal conclusion;
section 4 lists items for a lawyer.

TLDR
- Today FantasyDesk is an analysis layer on top of Sleeper. Hosting means we
  become the system of record (rosters, scoring, drafts), which is a big
  category change: uptime on game day, data licensing, and compliance become
  our problem.
- Recommended first slice: free-to-play, no-prize, college-only
  conference-limited Survivor + Pick'em (one pick per week, graded from a
  schedule/score feed). It reuses the existing Pick'em pattern
  (`docs/supabase_games.sql`), needs no draft, no waivers, no trades, and
  avoids player NIL/likeness because it uses teams, not athletes.
- Do not start with player-based college fantasy. It needs player-level
  licensing questions answered and a paid stats feed.

---

## 1. Hosted leagues

### 1.1 What "hosting" means (capability list)

| Capability | Notes |
|---|---|
| League creation and settings | roster slots, scoring, schedule, playoffs, keeper/dynasty rules |
| Invites and membership | invite links, join codes, co-commissioner, kicking, orphan teams |
| Drafts | snake/auction/linear, timers, auto-pick, queue, live room, rookie drafts |
| Scoring engine | per-stat scoring, stat corrections, lineup lock, tiebreakers |
| Waivers / FAAB | claim processing at a deadline, priority/rolling, free agents |
| Trades | proposal, accept, review/veto period, pick trading, roster limits |
| Commissioner tools | edit rosters, settings, force trades, reset, audit trail |
| Live scoring | in-game updates, projections, win probability |
| Notifications | push + email (draft on the clock, waiver results, trade offers) |
| Payments / prize pools | highest-risk area; see 1.6 and section 4 |

### 1.2 What we can reuse (verified in repo at origin/main)

- Live draft: `modules/live_draft.py`, `modules/live_draft_trade_evaluator.py`,
  `modules/draft_assistant.py`, `modules/draft_center_cards.py`, web routes
  `web-next/src/app/live-draft` and `draft-center`. Today these READ a Sleeper
  draft (`fetch_sleeper_draft_picks`) and compute pick order maps, needs,
  recommendations. Reusable: order math (`draft_slot_for_pick`,
  `build_draft_order_maps`), available pool, roster needs, recommendations.
  Not reusable: the Sleeper polling source; hosted needs our own pick
  write path, timer, and auto-pick.
- Valuations and trade engine: `modules/trade_*.py`, `trade_grade.py`,
  `valuation_authority.py`. Hosted trades would reuse these as advisor.
- Waivers and FAAB: `modules/waivers_logic.py`, `modules/faab.py` (advice
  based, not claim processing).
- Guillotine and survivor-like logic: `modules/guillotine.py`
  (`survival_status`, `weeks_survived`, `chop_line`) is analysis of existing
  Sleeper leagues, but the concept maps to a survivor format.
- Commissioner tools: `docs/commissioner-tools.md`,
  `modules/league_integrity*.py` (read-only integrity signals, Pro-gated).
  Not an admin console; hosted needs real commissioner write actions.
- Pick'em: `docs/supabase_games.sql` is the closest existing hosted-style
  pattern: per-user rows, RLS ownership, lock rules enforced in the API,
  grading computed server-side from a real feed, no money.
- Platform abstraction: `modules/platforms/` (sleeper, espn, yahoo). A
  `hosted` platform adapter implementing `base.py` would let existing
  screens (matchups, trade analyzer, standings) work on hosted leagues.
- Scoring/projections/news/weather/schedule: `player_projections.py`,
  `news*.py`, `game_weather.py`, `nfl_schedule.py`, `league_standings.py`,
  `matchup_win_probability.py`, `playoff_simulator.py`.
- Auth/billing/push: Supabase auth, `push_tokens.py`, `push_triggers.py`,
  `notification_center.py`, Stripe/RevenueCat entitlements.
- Prospects: `modules/college_scouting.py` and
  `docs/supabase_college_scouting.sql` (crowdsourced prospect grades). Note
  it deliberately has NO licensed college data feed ("never invent prospects").

### 1.3 Gaps (nothing exists today)

- No Supabase Realtime use found in web-next, mobile, modules, or services
  (grep for `.channel(` / realtime returned nothing). Everything is
  request/poll today.
- No write-path for rosters, transactions, or drafts that we own.
- No job runner for time-boxed processing (waiver runs, lineup locks,
  weekly rollover). Scheduled data refresh exists (players.db), but nothing
  transactional.
- No college stats/schedule feed wired in.

### 1.4 Staged path

| Stage | Format | Needs | Effort |
|---|---|---|---|
| 0 | Decide scope, legal review, data source | lawyer, feed trial | S (1 wk, mostly waiting) |
| 1 | Pick'em / Survivor (free, no prize), team-based | schedule + results feed, groups, leaderboard | M (3-4 wks) |
| 2 | Best-ball (auto-lineups, draft only, no waivers/trades) | draft room, scoring engine, stat feed | L (8-10 wks) |
| 3 | Redraft season-long (waivers, trades, weekly H2H) | waiver processor, trade flow, commissioner, live scoring | XL (12-16 wks on top of 2) |
| 4 | Dynasty (picks, taxi, rookies, multi-year) | multi-season rollover, pick ownership, contracts/keepers | L (8+ wks on top of 3) |

Effort is rough, one engineer plus agents, excludes legal waiting and store
review time. Stage 2 is the real jump: the first time we own a draft and a
scoring engine. Stage 3 is the hardest correctness surface (waiver ordering,
trade edge cases, stat corrections).

### 1.5 Data model sketch (Supabase)

All tables RLS-on; writes for money-free game state go through the FastAPI
service role (like Pick'em), clients only read what they own or are members
of. Hand-applied SQL per repo convention (no migration runner).

- `hl_leagues` (id, owner_id, name, sport `nfl|ncaaf`, format
  `survivor|pickem|bestball|redraft|dynasty`, settings jsonb, season, status,
  visibility, created_at)
- `hl_members` (league_id, user_id, role `owner|comm|member`, team_name,
  joined_at). RLS: members read own league's members.
- `hl_invites` (league_id, code, expires_at, max_uses)
- `hl_drafts` (league_id, type, status, order jsonb, pick_seconds,
  started_at) and `hl_draft_picks` (draft_id, pick_no, member_id, player_id,
  made_at, auto bool). Unique (draft_id, pick_no) is the concurrency guard.
- `hl_rosters` (league_id, member_id, slots jsonb) and `hl_transactions`
  (league_id, type, payload jsonb, created_at, status) as an append-only
  audit log.
- `hl_lineups` (member_id, week, slots jsonb, locked_at)
- `hl_matchups` (league_id, week, home, away, scores jsonb)
- `hl_picks` (league_id, member_id, week, subject_id [team or game],
  confidence int, locked_at, result). Hidden from other members until lock
  (same trick as `supabase_games.sql`: leaderboard built server side).
- `hl_survivor_state` (league_id, member_id, alive bool, used_teams text[],
  eliminated_week)
- `hl_events` (league_id, kind, payload, created_at): feed for realtime and
  push.
- Reference tables (read-only to clients): `ref_teams`, `ref_games`
  (kickoff, scores, status), later `ref_players`, `ref_player_stats`.

RLS principles: members read league-scoped rows; users write only their own
pick/lineup rows and only via API checks for lock; commissioner actions
only via API with audit rows; never trust client-supplied week/lock times.

### 1.6 Realtime: Supabase Realtime vs polling

- Survivor/pick'em: polling (or just refetch on focus) is enough. Picks lock
  at kickoff; scores update every few minutes at best.
- Live draft: needs low-latency fan-out and a server-authoritative clock.
  Use Supabase Realtime (Postgres changes or broadcast) on `hl_draft_picks`
  with a server-side timer worker; fall back to 2-3s polling on socket
  failure. Pick submission must be a single transactional RPC enforcing
  turn order and uniqueness.
- Live scoring: poll the feed server-side every 30-60s, write to
  `ref_games`/stats, and push deltas; clients refetch. Realtime optional.
- Uncertain: Supabase plan limits on concurrent realtime connections and
  message rates; confirm on our plan before committing for large drafts.

### 1.7 Infra and cost (order of magnitude, verify)

- Compute: a small always-on worker (draft timers, waiver run, score
  poller). Today the backend is FastAPI auto-deployed on merge to main; a
  worker with a cron/queue is new infra.
- Data feed: the largest cost driver. See section 3.
- Supabase: probable plan upgrade for realtime and storage if hosted leagues
  grow. Not quantified here.
- Support burden: disputes, stat corrections, commissioner mistakes. Hosted
  means we are the support desk.

### 1.8 Security and abuse

- Pick leakage before lock; multi-accounting to win free prizes; collusion in
  survivor pools; bot-scraped invite codes; draft sniping via client clock
  (server clock only); enumeration of leagues (UUIDs, no sequential ids).
- Rate limit join, create, and pick endpoints; email-verified accounts for
  creating leagues; report/block flow; moderation of league and team names.
- Auditability: append-only transaction log, commissioner action log.
- Privacy: only collect what is needed; age gate (see section 4).
- Payments: if ever added, do not handle pooled user funds ourselves.

---

## 2. College football formats (avoiding the 130+ team problem)

The problem: ~134 FBS teams means a flat player pool is huge, rosters are
unrecognizable to most fans, and depth charts/stats are thin and noisy. The
answer is to shrink the pool or make the unit a team, not a player.

| Format | Fun | Effort | Risk |
|---|---|---|---|
| Survivor (pick 1 team per week to win, cannot reuse a team, wrong = out) | High, simple, great weekly tension | S-M. Needs schedule/results only, no player data | Low if free. Elimination early shrinks engagement: add a "second chance" bracket or weekly reset pools. Money prizes raise legal risk |
| Conference-limited survivor/pick'em (e.g. Big Ten only, or Power-4 + Group of 5 pools) | High, easier to follow, fewer mismatches | S. Same as above with a team filter | Low |
| Pick'em / confidence (pick winners or spreads, weight by confidence) | High, familiar (bowl pools) | S-M. Spread data requires an odds source (see 3.4) | Spreads/odds data may drag in gambling-adjacent classification; use winner-only for the MVP |
| Bracket-style weekly head-to-head (users face each other, score by pick results) | Medium-high, social | M. Needs matchmaking and standings | Low-medium |
| Best-ball with a limited pool (draft 8-12 players from one conference or a curated top-N list, auto-optimized lineup) | High for football-heavy users | L. Needs player stats, draft room, scoring | NIL/likeness questions; stat feed cost; transfer portal churn mid-season |
| "Heisman race" style player pool (draft or pick from top ~40 players list) | Medium-high, cult appeal | M-L. Curated list, weekly stat scoring | NIL/likeness; list curation is editorial work; partial overlap with prop-betting territory |
| Full season-long college redraft | Low-medium for most | XL | Depth chart/stat noise, injury info scarce, large pool; not recommended |

Recommendation: ship conference-limited Survivor + Pick'em first (team-based,
no athlete names), then a conference best-ball/Heisman-style player format only
after legal review of athlete names and a stats feed decision.

---

## 3. Data sources and terms

Re-verify every row; fetch was partial.

### 3.1 CollegeFootballData.com (CFBD)

- Terms page fetched (https://collegefootballdata.com/terms). Findings:
  commercial use permitted, tier sets shared quota not rights; redistribution
  of API data as a dataset, mirror, proxy, or substitute API is prohibited;
  displaying reasonable portions of factual data inside a larger product is
  not redistribution; private caching and storage allowed (server-side
  caching and scheduled polling encouraged); attribution recommended not
  required ("Data provided by CollegeFootballData.com"); keys must not be
  embedded in browser or mobile code; do not present data as official NCAA
  or school data.
- Pricing/limits: the v2 GA blog (https://blog.collegefootballdata.com/api-v2-is-now-in-general-availability/)
  listed a free tier of 1,000 calls/month and Patreon tiers of 5,000, 30,000,
  75,000 calls/month, "subject to change". Current tiers live at
  https://collegefootballdata.com/api-tiers; I could not retrieve it.
  Treat the numbers as stale.
- Coverage is strong for teams, schedules, games, scores, rosters, stats,
  rankings, and betting lines endpoints exist per CFBD docs (verify).
  Realtime/live subscriptions were reported as top-tier only.
- Fit: best candidate for schedule/results MVP. Server-side only, cache in
  Supabase `ref_games`. Our users never touch the key.

### 3.2 ESPN unofficial endpoints

- Widely used undocumented JSON endpoints for scoreboards and rosters.
  Not a licensed API; ESPN terms generally restrict commercial use of data
  (I did not fetch their terms in this pass). Risk: they can break or block
  without notice and using them in a commercial product is a terms risk.
  The repo already has `modules/espn_leagues.py` for user-owned ESPN leagues,
  which is a different use. Recommendation: do not build a hosted product on
  unofficial ESPN endpoints. At most use as a non-critical fallback, after
  legal review.

### 3.3 Paid feeds: Sportradar, SportsDataIO

- Sportradar: pricing not public; third-party review sites rank it as
  top-priced; trial availability not confirmed for NCAAF. Enterprise sales
  process. Likely best for player-level + live play-by-play when licensing
  clarity matters.
- SportsDataIO: has a college football feed and a free trial
  (https://sportsdata.io/free-trial); pricing only partly public
  (https://sportsdata.io/developers/apis). Trial data is typically scrambled
  or limited; confirm. Contact sales for commercial terms and redistribution
  rights.
- A paid licensed feed may also carry (or help clarify) rights to display
  player names and headshots. Ask explicitly.

### 3.4 Schedule and odds

- Schedules/scores: CFBD (above) or a paid feed.
- Spreads/odds: CFBD lists lines (verify); dedicated odds APIs exist but
  were not researched here. Odds data raises the gambling-adjacency question
  for the product; keep winner-only for MVP.

### 3.5 NCAA stats and Sleeper

- NCAA stats: NCAA.com stats pages exist but I found no official public API
  or licensing terms; treat as not redistributable until confirmed.
- Sleeper: I found no evidence of Sleeper exposing college football leagues
  through its public API, and search results only showed consumer promo
  content. Treat as unsupported; verify directly against Sleeper's API docs.
  Competitors (Fantrax, Yahoo) do offer college fantasy per search results.

### 3.6 What we can legally redistribute / caching strategy

Not legal advice; based only on CFBD terms read above.
- Safe pattern: ingest server-side on a schedule, normalize into
  `ref_*` tables, serve derived, in-product views (standings, pick results,
  matchups). Do not expose a bulk dataset or an API that mirrors raw
  responses. Our existing `/v1/external` endpoints should NOT proxy CFBD raw
  data.
- Cache: poll schedule daily; scores every 1-5 minutes only on game days;
  freeze final scores; keep an audit snapshot of the score used for grading
  (avoids disputes after stat corrections). Budget calls against the monthly
  quota; batch by week and conference.

---

## 4. Legal and compliance flags (for a lawyer, no conclusions)

1. Athlete names, NIL, and likeness. College athletes can now be compensated
   for NIL, and EA Sports' college game licenses athletes via group licensing
   (OneTeam Partners), per press reports
   (https://www.si.com/college/2024/02/22/college-football-players-opt-into-ea-sports-video-game-nil-deal,
   https://www.nationalfootballpost.com/college-football/reports-ea-sports-increases-player-payments-for-college-football-26/).
   I found nothing on whether fantasy operators license athlete NIL, or
   whether factual stats use is protected the way it is for pros. Flag:
   right of publicity by state, school/conference marks (logos and team names
   are trademarks), headshots, and whether a team-only product avoids most of
   this. Also unresolved: how recent developments (revenue sharing, House
   settlement era) change anything.
2. State fantasy/gambling law. Free-to-play, no-prize contests are
   generally treated differently from paid contests, but this varies and
   some states regulate or restrict paid fantasy or contests heavily.
   Survivor and pick'em with entry fees or prizes can be treated as gambling
   or lottery (consideration + chance/skill + prize). Secondary sources claim
   a handful of states restrict DFS severely; these are low-confidence. Need
   a state-by-state matrix from counsel, plus sweepstakes/promotion rules
   (no-purchase-necessary, registration, bonding in some states) if any
   prizes exist.
3. Apple App Store Guideline 5.3. Apple developer forum threads summarize
   5.3 as requiring licensing and geo-restriction for real-money gaming,
   disallowing IAP for gaming credit, and requiring sweepstakes/contests to
   be sponsored by the developer; one thread reports a free prediction app
   with prizes being classified under 5.3.4
   (https://developer.apple.com/forums/thread/825845). Read the live
   guideline text; we have an iOS app mid-review, so avoid anything that
   triggers a new rejection of the existing binary.
4. Google Play. Real-money gambling/DFS apps require Google approval and
   licensing per its gambling policy
   (https://support.google.com/googleplay/android-developer/answer/9877032).
   Free-to-play with no prizes avoids that path; confirm.
5. Age. Define a minimum age (13 for COPPA reasons is a floor, 18 safer if
   any prize exists). Fans include minors; players are mostly adults but
   some college athletes may be under 18 (rare). Counsel to advise on
   whether any age gate is needed for athlete data.
6. NCAA rules. NCAA has positions on athlete betting and on sports wagering
   marketing; I did not verify current policies. Flag any odds/spread
   display and player prop-style features specifically.
7. Privacy and payments. Hosted leagues collect more user data (league chat,
   usernames); review our privacy policy (`modules/legal_pages.py`). If
   money ever flows (entry fees, payouts), that implicates money
   transmission/KYC; avoid.
8. Content/UGC: league chat, names, reporting and takedown.

Recommendation: free-to-play, no prizes, no entry fees, no odds display in
the MVP. Revisit only after counsel reviews. Even "prizes" like gift cards or
paid-tier credits should wait for counsel.

---

## 5. Product fit and build order

Strengths to connect: trade and lineup intelligence, valuations, verdicts,
news, and league intelligence. Survivor/pick'em can reuse the GM voice
(pick advice with multi-factor reasoning: opponent strength, rest, injuries,
weather via `game_weather.py`, how many teams you have left to burn). That
gives a differentiated "smart survivor" over a plain pool app. Later, best-ball
and redraft can reuse the trade analyzer and lineup optimizer as advisors on
leagues we host.

Existing-league path remains primary revenue; hosting must not regress the
Sleeper analysis experience. Per standing rules, every web change ships with
the iOS/Android equivalent, and shared components are reused.

### First shippable slice (recommended)
Free, no-prize "College Survivor + Pick'em", conference-limited pools:
- Create or join a pool by invite code; choose a conference or all-FBS
  weekly menu of ~10-15 games.
- One pick per week, locked at that game's kickoff; survivor never reuses a
  team; optional pick'em with a confidence rank.
- Server-graded from CFBD results; leaderboard with picks revealed at lock.
- GM advice card per pick (opponent, venue, weather, teams-remaining).
- Push: pick reminder, lock soon, result.
- Effort: M, about 3-4 weeks including web + mobile parity. Legal pre-check
  in parallel.

### Build order
1. Counsel review (team-only, free, no prizes) and CFBD tier decision.
2. Schema (`hl_*` minimal subset), schedule ingest + cache, grading job.
3. Survivor/pick'em API + web + mobile, push.
4. Measure retention through one season window.
5. Decide on player-based format (conference best-ball) based on usage and
   legal answers; pick a licensed stats feed.
6. NFL-side hosted best-ball (re-uses draft room), then redraft, then
   dynasty only if demand justifies the ops burden.

### Questions for coridian_
1. Is the goal to host real leagues long-term (rosters/waivers/trades), or
   is a lightweight college game the actual priority?
2. Free-to-play with no prizes only for now? Any appetite for prizes later
   (this changes legal and store risk a lot)?
3. Team-based (survivor/pick'em) first, or must it be player-based fantasy
   from day one?
4. Which scope: one conference, Power-4, or all FBS with weekly curated
   menus? Is FCS in or out?
5. Budget: OK to pay for a data feed (CFBD tier now, possibly Sportradar or
   SportsDataIO later) and for a lawyer consult?
6. Timeline: aim for this fall's remaining season/bowls, or build for next
   season's kickoff? (Bowl-season pick'em could be a quick pilot.)

## Sources
- CFBD terms: https://collegefootballdata.com/terms
- CFBD v2 GA post: https://blog.collegefootballdata.com/api-v2-is-now-in-general-availability/
- CFBD usage and access: https://apinext.collegefootballdata.com/usage-and-access
- SportsDataIO: https://sportsdata.io/developers/apis , https://sportsdata.io/free-trial
- Apple dev forum summaries of 5.3: https://developer.apple.com/forums/thread/825845 (secondary; read the official guidelines)
- Google Play gambling policy: https://support.google.com/googleplay/android-developer/answer/9877032
- EA/NIL press: https://www.si.com/college/2024/02/22/college-football-players-opt-into-ea-sports-video-game-nil-deal
- DFS state-law roundups (low confidence): https://deadspin.com/dfs-legal-states/
