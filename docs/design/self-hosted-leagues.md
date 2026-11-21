# Self-hosted real fantasy leagues (design, 2026-11-17)

Status: **design for owner review. No product code changed.** Nothing here is built until the owner approves the open
decisions in section 9. Web + app parity applies to the eventual build (every web surface ships with its iOS/Android
twin, exceptions called out).

Research method: public docs and press as of 2026-11-17 (links inline); repo read of `docs/audits/2026-11-public-sim-leagues.md`,
`docs/audits/2026-11-dependency-and-freshness.md`, `docs/commissioner-tools.md`, `docs/box-runbook.md`, `modules/`.
Competitor facts that I could not confirm from a primary source are marked **(unverified)**. Most review sites are
affiliate content; I weighted vendor docs and news over them. Re-verify before any of it appears in marketing.

---

## 1-page summary

**What.** Let people create and play full NFL fantasy leagues on FantasyDesk itself (draft, lineups, waivers, trades,
playoffs, chat), instead of only analysing leagues that live on Sleeper/ESPN/Yahoo/MFL/Fleaflicker. Real Sleeper leagues
stay on Sleeper; self-hosted leagues are the path to independence from third-party platforms.

**Decided (not reopened here).**
- Playing in a self-hosted real league is **free**. Advanced metrics and advice are **Pro** (owner, 2026-11-16).
- Public SIM leagues are a separate product (invite + public lobbies, 48h/24h weeks, creator needs Premium, 1 free sim
  season, storyline consequences). We reuse its machinery (seats, clock worker, invites, notifications), not its rules.

**Why it can win.** Every incumbent is either mass-market and shallow (ESPN, Yahoo), polished but light on analytics
(Sleeper), or deep on customization but dated (MFL, Fleaflicker). None puts decision-grade analytics *inside* the league:
win-odds ranges on the matchup, a trade grade at the moment you send an offer, FAAB bid guidance, dynasty asset values, recaps.
We already build these for other platforms' leagues. Hosting the league means the analytics get the league's *native*
data (real-time, every transaction, commissioner rules) instead of a scraped read.

**Biggest findings.**
1. **Sleeper's API is "free for non-commercial use only"; commercial use requires contacting Sleeper** ([docs.sleeper.com](https://docs.sleeper.com/), fetched 2026-11-17).
   That already affects our current product, and makes the Sleeper import (one-tap migration) and any Sleeper-derived live scores a
   licensing question to settle first. See decision 1.
2. **Live scoring is the hard dependency.** We have no licensed real-time NFL stat feed today (nflverse is post-game). Options range from
   $10-40/month small vendors with unclear redistribution rights to enterprise licences (Sportradar / SportsDataIO, quote only).
3. **The engine mostly exists.** The Sim League design already specifies seats, a clock worker, invites, autopilot, push, human-human trades
   and commissioner tools. A real league is "the same league core with real NFL stats as the input and no simulation".
4. **Single box is acceptable for the MVP build but not for a Sunday-afternoon product.** A league tool is judged on game day. We need an off-box
   standby for the scoring/lock worker and a documented degraded mode before the first live season.

**Recommended path.** (a) settle Sleeper/stat-feed licensing; (b) ship a **Friends League MVP**: invite link, snake draft, scoring presets +
custom, rolling/FAAB waivers, trades with a review window, weekly matchups, playoffs, push; (c) add one-tap Sleeper import
and the Pro analytics layer; (d) auction, best ball, dynasty/keeper depth, public lobbies. About **8-10 weeks for the MVP, 24-30 weeks to full**
(web + app together), assuming a live-score source is chosen first. Target the **2027 preseason**; the 2026 season is at week 11, too late to onboard drafts.

**Needs from the owner:** the 12 numbered decisions in section 9 (each has a recommendation).

---

## 2. Competitive landscape

"What's missing" is judged for a *serious* player (dynasty/keeper, deep scoring, advice). Sources fetched 2026-11-17.

| Platform | Does well | Missing for a serious player | Confidence |
|---|---|---|---|
| **Sleeper** | Fast mobile-first UX, chat/social is central, rookie-only drafts, taxi squads, tradable picks, configurable waiver hold days. Ranked the top dynasty host in a 2026 roundup ([Draft Sharks](https://www.draftsharks.com/kb/best-fantasy-football-websites)); own pitch: [Sleeper blog](https://blog.sleeper.app/what-features-does-sleeper-have-that-other-platforms-dont-have/). | Analytics are shallow (no built-in win-odds ranges or trade grading; third-party tools fill the gap). Reviews say Underdog is better for best ball. IDP and exotic scoring specifics not verified **(unverified)**. | medium (reviews are affiliate-heavy) |
| **ESPN** | Mass reach; now the NFL's official fantasy platform, absorbing NFL Fantasy (commissioners can import NFL Fantasy leagues with settings/members/history where available) ([ESPN Press Room](https://espnpressroom.com/feature/nfl-fantasy-is-moving-to-espn-fantasy-your-questions-answered/), [Cord Cutters](https://cordcuttersnews.com/the-nfl-is-phasing-out-its-fantasy-app-and-handing-fantasy-football-to-espn-heres-what-players-need-to-know/)); new 2026 Knockout leagues ([Laughing Place](https://www.laughingplace.com/entertainment/espn-fantasy-football-knockout-leagues/)). | **No dynasty leagues**; scoring flexibility described as static ([dynasty platform roundup](https://dynastyleaguefootball.com/dynasty-draft-guide-2026-dynasty-platforms/), read via search summary; direct fetch returned 403). | medium |
| **Yahoo** | Free, accessible, old (1999), polished app. 2026: commissioner custom scoring per stat and position (kick/punt return yards), optional "Team Offense" position ([Fantasy Nerds, 2026-08-26](https://fantasynerds.com/news/story/2026/08/26/yahoo-fantasy-football-unveils-advanced-custom-scoring-options-for-commissioners-1605916)). | Dynasty/keeper depth and commissioner detail not confirmed **(unverified)**; analytics are generic projections. | low-medium |
| **Fleaflicker** | Simpler alternative to MFL: taxi squads, keepers, up to 24-team leagues, league import from ESPN/Yahoo (2023 guide). | Dynasty is "technically possible but far from ideal unless casual with a strong commissioner" ([2026 roundup](https://dynastyleaguefootball.com/dynasty-draft-guide-2026-dynasty-platforms/)); dated UI; no pricing found **(unverified)**. | low-medium |
| **MyFantasyLeague (MFL)** | Deepest customization; long-standing dynasty favorite for hardcore players (same roundup). | Steep learning curve, dated UX. One competitor brief lists 2026 commissioner pricing of $99.95-$219.90 and a prepayment rule for future-year pick trading ([Alpha Leagues brief](https://alpha-pricing-brief.pages.dev/), single source, **unverified**). A rumored 2026 overhaul is only a forum post ([Footballguys forum](https://forums.footballguys.com/threads/commissioners-are-awesome.816968)). | low |
| Context: **Fantrax** | Closest rival to MFL on customization (same roundup). | Complexity. Not requested, but the real "serious" competitor. | low |

**Pattern.** Mass-market platforms optimize onboarding and reach; hardcore platforms optimize configurability; *nobody competes on built-in decision
analytics*. Third-party tools (FantasyPros, Dynasty Nerds, etc.) fill that gap by syncing to the league, which is the gap we monetize today.
**Our wedge:** a league where the analytics are first-class, mobile-first, and not a paid add-on bolted onto someone else's league.

Follow-ups before any external marketing: read each platform's official help pages for current settings and fees (Fleaflicker and Yahoo help pages
were not reached in this pass) and run a hands-on feature matrix.

---

## 3. Why switch: analytics and advice built into the league

Principle: the **league is free; the judgment is Pro**. Free users get a complete, competitive, unhandicapped league (so a mixed league of free
and Pro friends works); Pro users get the numbers and advice that win. Never lock a free manager out of a league function.

| Feature (in-league) | What the user sees | Free | Pro |
|---|---|---|---|
| Matchup win odds + projection ranges | Matchup card: your score vs opponent, win probability with a P10-P90 range, who has plays left. The engine exists for imported leagues (Playoff Odds) | live score, plain projected total | win % with ranges, "what swings it" |
| Lineup guidance | Start/sit with reasons (usage, matchup, injury, role) | roster and projected points | ranked recommendations with confidence and why |
| Trade grades at offer time | While composing an offer: both-sides value, fairness, effect on each team's title odds | the full trade flow | grade, odds delta, counter-offer suggestions (the receiver sees a grade only if they are Pro) |
| Smart waivers / FAAB guidance | Suggested bid range (floor/likely/ceiling), who else needs the player, replacement gain | claims and bids | bid guidance, drop candidates, stash vs stream |
| Storylines and recaps | Weekly recap, rivalries, power rankings, awards (reuse `league_recaps`, `league_storylines`) | recap text | deeper analytic recaps, shareable cards |
| Dynasty tools | Asset values, aging curves, pick values, rebuild/contend posture | roster + picks | values, trade finder, multi-factor advice (context, competition, need, posture) |
| League integrity | Existing Commissioner tools are Pro and not commissioner-gated (`docs/commissioner-tools.md`) | n/a | edge case, decision 11 |
| Sim tie-ins | "Sim this trade/draft/season forward" from a real roster | one free sim season (decided) | per sim rules |
| Draft room | Live board, ADP, queue | board, queue, ADP | pick advice, auction price targets |

The decided boundary: **free = the league operates; Pro = analytics and advice**. Edge cases are decision 11.

Why this beats "sync an outside tool to a Sleeper league": native real-time data with no scraping or rate limits; one account and one
notification stream; advice at the *moment of action* (sending the offer), not in another tab; we own the rules, so advice is exact for custom scoring.

---

## 4. Migration: Sleeper import and cross-platform

### 4.1 What the Sleeper API gives us
Public, no auth, read-only ([docs.sleeper.com](https://docs.sleeper.com/), 2026-11-17). Endpoints: user, user leagues by season, league, rosters, users,
`matchups/<week>`, `winners_bracket`, `losers_bracket`, `transactions/<round>`, `traded_picks`, league drafts, draft, draft picks, draft traded picks,
`state/nfl`, players, trending. Guidance: under 1,000 calls/min; `/players` about once a day (about 5 MB).

| Import need | Sleeper exposes | Gap / how we handle |
|---|---|---|
| League settings (roster slots, scoring, waiver type, playoffs) | league object: `roster_positions`, `scoring_settings`, `settings` | Map to our schema; unmodelled settings are listed in an "unsupported settings" report before import. Field-by-field spike needed. |
| Members and teams | users + rosters (owner ids, team metadata) | Display names only; imported members have no FantasyDesk account until they claim a seat by invite. |
| Rosters, taxi, IR | rosters: `players`, `starters`, `reserve`, `taxi` | Good. |
| Keepers | roster keepers and draft picks flagged keeper **(unverified; confirm in spike)** | Keeper *rules* (cost escalation) are commissioner conventions not fully in the API; the commissioner confirms them. |
| History (past seasons) | `previous_league_id` chain, per-week matchups, brackets, transactions, drafts | Good; makes league history and trophies portable. |
| Draft, picks, traded picks | draft, picks, traded picks | Good; future pick ownership from `traded_picks`. |
| FAAB balances | league waiver budget + roster budget used | Derivable. |
| Trade vetoes/votes, chat, notes, polls | not exposed | Lost on import; stated in the import preview. |
| Auth / admin | none; read-only | Import runs from a public league id, so **we need an in-product ownership check** (importer must be a member, verified by Sleeper username) and a notice to members. |

**One-tap flow:** pick from the user's Sleeper leagues (we already list them) or paste a league id; preview what imports and what does not;
confirm; invite the other managers by link; they claim their imported team. Matchups continue from the current week.

### 4.2 Licensing caveat (blocking, decision 1)
Sleeper's API is free for non-commercial use only; commercial use requires contacting Sleeper. The dependency audit already lists Sleeper
as "no written commercial licence" (`docs/audits/2026-11-dependency-and-freshness.md` section 3). A one-time, user-initiated import of the user's own league is
the most defensible use but should be confirmed in writing. **The import must not become a standing sync**, and a migrated league must not depend on
Sleeper for live scores (section 6).

### 4.3 Other platforms
Read-only adapters for ESPN, Yahoo, MFL and Fleaflicker already exist (`modules/espn_leagues.py`, `mfl_leagues.py`, `fleaflicker_leagues.py`) and could seed
import-to-self-host. ESPN and Yahoo access are unofficial or OAuth-gated, so they are a fast follow, not MVP. Import is table stakes, not a differentiator:
ESPN imports NFL Fantasy leagues and third-party FanDraft imports from ESPN/Yahoo/Sleeper/MFL/Fantrax/CBS/Fleaflicker ([FanDraft](https://www.fandraft.com/whats-new/)).

---

## 5. Core league features and options

Each decision: options, then the **recommendation (R)**. Phases refer to section 8.

### 5.1 Creation and invites
- Options: (A) invite link + 6-char code only; (B) A plus public lobby; (C) B plus email/contact invites.
- R: **A in MVP**, B after moderation exists (reuse sim lobby machinery and its Apple 1.2 kit), C later. The commissioner picks a preset, gets a link; unclaimed seats stay open;
  the draft cannot start with open seats unless the commissioner allows CPU autodraft seats. Deep link `fantasygmlab://league/join/<code>` mirroring sim join. No Premium needed to create (decided: free).

### 5.2 Formats
- Redraft (MVP), **keeper** (configurable count and round cost), **dynasty** (rookie draft, taxi, pick trading), **best ball** (auto-optimal lineups), **superflex** (a roster slot), **TE premium** (scoring modifier), **IDP** (positions + scoring; `idp_league_values.py` already values IDP).
- R: superflex and TE premium at MVP (configuration); best ball and dynasty/keeper in Phase 3; IDP Phase 4.

### 5.3 Draft types
- Snake (MVP), **slow draft** (long pick clock, 4-8h; Phase 3), **auction** (nomination order, budgets, timers, proxy bids; Phase 3), **rookie/startup** drafts (with dynasty, Phase 3).
- Pick clock: R commissioner chooses from presets (60/90/120s live; hours for slow). Autopick from queue, then public-information ADP + need (as in sim drafts). Draft order random/manual/lottery. Reuse the sim draft room patterns (`modules/sim/game_draft.py`).

### 5.4 Scoring
- Options: (A) presets only; (B) presets plus per-stat custom; (C) B plus bonuses (yardage tiers, long TDs) and per-position overrides.
- R: **B plus simple bonuses at MVP**, per-position overrides next. Yahoo just shipped per-position custom scoring (above), so serious players expect it.
  Scoring is a **versioned object frozen at league start** so every score is reproducible. Stat corrections re-score until a finality date (section 6).

### 5.5 Lineup locks
- Options: (A) per-game lock at kickoff (Sleeper/ESPN/Yahoo norm); (B) whole-slate lock; (C) weekly lock at first kickoff.
- R: **A**. Needs reliable kickoff times (nflverse schedule is already cached) and a server-side authoritative clock.

### 5.6 Waivers
- Options: rolling priority, FAAB (blind bids), continuous first-come, free agency after waivers clear.
- R: **FAAB + rolling at MVP**, continuous after. Configurable run time and waiver period for dropped players, processed by the idempotent league worker. FAAB guidance is Pro; free users still bid.

### 5.7 Trades
- Review options: (A) none; (B) commissioner approval; (C) league vote with veto; (D) timed review (24-48h) with veto threshold.
- Deadline: week-based, commissioner-set. Picks tradeable in dynasty. Trade-spam and collusion safeguards reuse sim section 2.8.
- R: **D with commissioner override**. Fairness *information* is Pro; the platform never auto-blocks for "unfairness" in real leagues, collusion flags go to the commissioner.

### 5.8 Commissioner tools
- Edit rosters, force trades, adjust scores, change settings mid-season (audited), pause league, remove/replace manager, set deadlines, announce.
- R: **every commissioner action is logged and visible to the league**, a trust differentiator over incumbents. The existing league-integrity tooling (`docs/commissioner-tools.md`) becomes first-class.

### 5.9 Playoffs
- Options: weeks 15-17 vs 14-16 (avoid Week 18), 4/6/8 teams, 1- or 2-week rounds, consolation brackets, byes, tiebreakers (points for, head-to-head, division).
- R: presets for 4 and 6 teams with weeks derived from the schedule at MVP; consolation/toilet bowl in Phase 3.

### 5.10 Chat and social
- Options: (A) none; (B) reactions + templated notes; (C) free-text league chat with the Apple 1.2 kit; (D) C plus trade chat, GIFs.
- R: follow the sim decision: **B at MVP, C in Phase 3.** Real leagues are social, so chat is competitive table stakes (Sleeper's strength); do not push it past Phase 3.

### 5.11 Notifications
- Reuse `push_tokens`, the push-safety layer and `docs/canonical-notification-center-contract.md`.
- Types: draft starting, on the clock, lineup hole before kickoff, starter injury news, waiver result, trade offer/answer, close-matchup swings, recap.
- R: per-type toggles; exempt "on the clock" and "offer received" from the global cap (as decided for sim); game-day score alerts opt-in.

---

## 6. Live scoring and data layer

Context: `docs/audits/2026-11-dependency-and-freshness.md` (independence plan) says we can own player and game data but not Sleeper's league data.
A self-hosted league *is* the league data, so that half is ours. What we lack is a **licensed real-time NFL stat source**:
nflverse is post-game, and our in-season weekly stats today come from Sleeper's stats endpoint, which is under the same non-commercial terms.

| Option | Latency | Cost (public info) | ToS / licensing | Risk |
|---|---|---|---|---|
| **A. Sleeper stats endpoint** (as today) | minutes, undocumented | free | non-commercial only; the stats endpoint is not in the public docs | Cannot underpin a commercial league product without a written licence |
| **B. Small-vendor APIs** (Goalserve, Highlightly) | seconds to a minute | Highlightly publishes $0 (5 req/min), $9.99 (60/min), $39.99 (600/min) per month ([Highlightly](https://highlightly.net/blogs/best-nfl-apis-in-2026)); Goalserve is tiered ([Goalserve](https://goalserve.com/sport-data-feeds/NFL-api/prices)); 2026-11-17 | vendor terms generally cover display; fantasy scoring redistribution and NFL data rights must be confirmed in writing | Medium: cheap and quick; uncertain rights and fantasy-grade accuracy |
| **C. Enterprise licensed feeds** (Sportradar, SportsDataIO) | seconds, push/stream | quote only (no public pricing found) | explicit commercial licences; fantasy is a known licence class | Low technical risk, highest cost, needs a contract |
| **D. Scrape ESPN/NFL.com unofficial endpoints** | seconds | free | against terms; can break or block anytime | Not recommended |
| **E. Hybrid (R)** | seconds | B or C live; nflverse/own for reconciliation | per vendor | Live display from a licensed vendor; **final scores from reconciled official stats** |

**Recommendation:** request C quotes in parallel with a trial of B (decision 2). Hide the vendor behind our own `LiveStatsProvider` interface so a swap is config,
and keep nflverse as the post-game reconciliation (stat corrections land Tuesday/Wednesday).

**Failure handling (game-day contract).**
- If the primary feed is stale for more than N minutes in a live window, fall back to the secondary and show "scores delayed" on the matchup, never a silent wrong zero.
- Never overwrite good data with garbage (same contract as the dependency audit's fault-injection tests; add the live feed to them).
- Scores are **provisional until a finality date**; the commissioner can freeze a week. All changes go through an append-only score-event log so they are explainable.
- Game-day watchdog: alert if no stat update arrives inside a known game window (we have the schedule) and page the owner, not just open a GitHub issue.
- Cost control: poll only in game windows (about 5 a week), cache a normalized per-game stat blob in Redis, fan out to leagues in-process. Cost scales with games, not leagues.

---

## 7. Architecture sketch (current stack)

Stack today: FastAPI `services/mobile_api_service.py` on a **single self-hosted box** (docker compose: API, Redis, Caddy; `docs/box-runbook.md`), Supabase for
auth/Postgres/billing, GitHub Actions for crons. (The older sim design mentions Render for the API and worker; this doc follows the box runbook, mismatch flagged in decision 12.)

**Reuse, don't rebuild:** the league core from the Sim League design (seats, invite codes, claim flow, clock worker with `claim_due` leases, autopilot,
push, polled `pulse`), `modules/league_*` (standings, recaps, storylines, calendar, history), the notification center, valuation engines.
Key difference from sim: **no simulation engine and no hidden info**; state comes from real stat events plus league transactions.

**Data model (Supabase Postgres, hand-applied SQL as with the sim; backend is the only writer, RLS as defense in depth).**

| Table | Purpose |
|---|---|
| `leagues` | id, name, season, status, commissioner, invite_code, source (`native` / `sleeper_import`), settings jsonb (versioned, frozen scoring + roster rules) |
| `league_members` | league_id, user_id (null until claimed), team name, role, status |
| `league_teams`, `rosters`, `roster_slots` | current roster state incl. taxi/IR |
| `league_events` | append-only log of every transaction (pick, add/drop, claim, trade, lineup set, commissioner edit); unique `(league_id, command_id)` for idempotency |
| `drafts`, `draft_picks`, `draft_queue` (+ `bids` for auction) | draft state |
| `waiver_claims`, `trades`, `trade_votes` | pending transactions with deadlines |
| `matchups`, `score_events` | schedule; append-only fantasy score log derived from stats (provisional/final flag) |
| `player_game_stats` (shared by all leagues) | normalized live + final stat lines with source and corrected_at |
| `league_messages`, `reports`, `blocks` | chat and moderation (Phase 3) |
| `league_jobs` | scheduler: waiver runs, lineup locks, scoring windows, playoff advance |

**Scheduler:** one always-on worker (the sim worker pattern) plus a watchdog. Locks and waivers are time-triggered and idempotent (re-running a tick is harmless).
The server clock is authoritative; clients never decide a lock.

**Live scoring path:** provider -> normalizer -> `player_game_stats` (Redis hot copy) -> per-league scorer (pure function of frozen scoring + stats) ->
`score_events` -> ETag'd `pulse` endpoint polled by web/app (websockets later via Supabase Realtime broadcast).

**Scale assumptions.** First season: 500-2,000 leagues, 12 teams, about 8,000-25,000 humans. Scoring a league-week is a few milliseconds of pure compute over roughly 12 x 20 slots.
The real load is the **kickoff-window spike** (everyone opens the app at 1:00pm ET Sunday): `pulse` polling, push fan-out, and the scorer running every 30-60s per active league.
With in-process caching of the per-game stat blob and `pulse`, 2,000 leagues fits one worker plus one API container; 10x is a vertical upgrade plus read caching
(consistent with the sim doc's $50 to $500/month infra estimate; stat-vendor cost is separate and likely dominates).

**What the single box means here.** Today a box outage degrades analytics. For hosted leagues it breaks the *rules engine on game day*: missed lineup locks, unprocessed waivers,
frozen scores. Required before the first live season, in order:
1. League state recoverable from Supabase alone (already off-box).
2. A **standby** (second small host or managed container) that can run worker + API from the repo + Supabase, with documented manual failover (RTO under 30 min in game windows).
3. **Catch-up semantics**: a late tick processes in order and never double-applies (idempotent keys); lock enforcement uses the game's *kickoff time*, not the time of processing.
4. Backups/PITR for league tables, a tested restore, and a game-day status page.
A multi-hour Sunday outage would be a trust-ending event for a product whose promise is "your league just works".

Compliance: Apple guideline 1.2 for UGC (names, chat) reused from the sim kit; **no real-money entry fees or prizes** in v1 (consistent with sim; contest rules vary by state and store). Leagues that collect dues do so off-platform (decision 10).

---

## 8. Phased roadmap

Sizes: S under 3 days, M about 1 week, L 2-3 weeks, XL 4+ weeks (web + app together). Assumes the league core is built once and shared with sim leagues; if
the sim league core is not yet built, add about 6-8 weeks (its Phase 1).

| Phase | Scope | Size | Risk |
|---|---|---|---|
| 0 Prereqs | licensing answers (Sleeper, stat vendor); vendor trial and `LiveStatsProvider`; standby-host plan; scoring engine validated against historic league scores | M | M (external) |
| 1 MVP: Friends redraft league | league tables; create/invite/claim; presets + per-stat custom scoring; snake draft (live + queue + autopick); lineups with per-game locks; rolling + FAAB waivers; trades with review window; weekly matchups; basic playoffs; commissioner log; push; reactions; league home with live scores; web + app | XL (about 8-10 weeks) | H (live scoring, locks, two clients) |
| 2 Migration + Pro layer | Sleeper one-tap import (settings, rosters, history, picks, taxi); win-odds ranges; trade grade at offer time; FAAB guidance; in-league recaps/storylines; Pro gating | L-XL (5-6 weeks) | M |
| 3 Formats and depth | keeper, dynasty (rookie draft, pick trading, taxi), best ball, auction, slow drafts, consolation brackets, free-text chat + moderation kit, public lobbies | XL (8-10 weeks) | H (auction timers, moderation) |
| 4 Breadth | IDP, ESPN/Yahoo/MFL import, spectators, season cards, sim tie-ins, commissioner extras | L-XL (6-8 weeks) | M |
| Ongoing | stat-correction handling, offseason tooling, year rollover | M per season | M |

Total: about **8-10 weeks to a usable MVP; 24-30 weeks to full**, serial. With 2-3 agents in parallel, Phase 1 backend can overlap Phase 2 analytics wiring.
Gate: no **public** lobbies until a moderation owner and rota exist (sim decision 5). Launch: closed beta during 2027 preseason mock drafts, live for 2027.

---

## 9. Open decisions for the owner

Each has a recommendation. Already-decided items (free to play, Pro analytics, sim rules) are not repeated.

1. **Sleeper licensing.** Ask Sleeper in writing for commercial permission for (a) user-initiated league import and (b) any continuing API use? Options: ask now; proceed with one-time user-initiated import only; avoid Sleeper for hosted leagues. **R: ask now; scope the MVP so hosted leagues never depend on Sleeper at runtime.**
2. **Live stat source.** Small vendor first, enterprise licence later, or enterprise immediately. **R: trial a small vendor and request enterprise quotes; abstract behind `LiveStatsProvider`; budget $0-$40/month to prototype, a real licence before public launch.**
3. **Launch season.** 2027 preseason vs a rushed 2026 beta. **R: 2027 preseason; use the rest of 2026 for Phase 0 and a closed alpha on historic data.**
4. **MVP format scope.** Redraft only, or include keeper/dynasty at MVP. **R: redraft only (superflex and TE premium as configuration); pull dynasty into Phase 2 if the owner's group plays dynasty, since that is where our analytics are strongest.**
5. **Trade review default.** Commissioner approval, league vote, or timed review with veto. **R: 24h timed review with veto threshold and commissioner override, configurable.**
6. **Lineup lock model.** Per-game, weekly, or commissioner-chosen. **R: per-game default; whole-slate as a later option.**
7. **Chat timing.** Reactions-only MVP then free text in Phase 3, or free text at MVP. **R: Phase 3; pull forward only if moderation staffing exists.**
8. **Hosting hardening.** Is a standby host and tested game-day failover required before launch, and at what budget? **R: yes, about $20-60/month; non-negotiable for hosted leagues.**
9. **Public lobbies for real leagues.** Private (invite) only through launch, or public lobbies in Phase 3. **R: private only through launch; public lobbies after moderation exists.**
10. **Money.** Entry fees, prize pools, dues tracking? **R: none in v1 (consistent with sim); revisit only with legal advice; commissioners can post rules/notes text.**
11. **Pricing edge cases (Pro vs free).** Do "commissioner extras" count as advanced? Specifically: (a) league-integrity/tanking tools (today Pro, any league), (b) collusion/fairness flags in a hosted league, (c) the commissioner audit log and history exports, (d) custom scoring beyond presets, (e) multi-league limits. **R: free = everything needed to *run* a league fairly (audit log, rule enforcement, custom scoring, history export, unlimited leagues); Pro = analytics and advice, including integrity *analytics* (tanking/collusion signals) and trade grades. Never gate a rule a member must follow.**
12. **Where the always-on worker runs.** The sim design assumes a Render worker; the runbook says a single box. **R: the box plus a Supabase `pg_cron` watchdog and the standby from decision 8; do not add Render for this.**

Follow-ups (not owner decisions): competitor help-page verification (Fleaflicker/Yahoo/MFL fees), the Sleeper-to-schema mapping spike, Apple age-rating review (shared with sim).

---

## 10. Risks (short)

- **Licensing** (Sleeper non-commercial, NFL stat rights): could force vendor spend or scope change. Mitigation: Phase 0, decisions 1-2.
- **Game-day reliability** on a single box: mitigations in section 7.
- **Cold start:** leagues are invite-driven and sticky once running, but a migration needs a whole league's buy-in. Mitigation: one-tap import, invite flow, free to play.
- **Scoring correctness:** a wrong score is a trust failure. Mitigation: reproducible versioned scoring, reconciliation against official stats, commissioner freeze.
- **Moderation/UGC** (names, chat): the sim kit, phased as above.
- **Scope creep:** incumbent feature lists are long; MVP is intentionally redraft-first.
