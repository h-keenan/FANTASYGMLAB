> **Historical / partly obsolete (2026-10):** this document describes the retired Streamlit web app (`app.py`, `streamlit run`, `/_stcore/health`, `st.session_state`), which has been removed. The production web app is `web-next/` (Next.js) on the FastAPI services. See [`streamlit-removal-2026-10.md`](streamlit-removal-2026-10.md). Streamlit-specific details below are no longer current.

# Engagement and retention brainstorm: October 2026

Written 2026-10-21 against `main` at `3c427fa5`. This is a brainstorm and a
recommendation, not a spec. Nothing here is built yet.

The question from the product owner: **"What do we need to keep engagement
and keep users on our site?"** The owner floated a season simulator. This doc
designs that, lists the other ideas worth weighing, ranks everything, and sets
clutter rules.

Inputs: `docs/competitive-audit-2026-10.md`, the owner's post-launch roadmap
PDF (treated as ideas, not instructions), and a code check of `main`.

---

## 0. Where we stand (verified in code, 2026-10-21)

| Item | Status | Evidence |
|---|---|---|
| GM Plan / GM Orb action center | **Live** (W, M) | `web-next/src/app/gm-plan`, `modules/gm_plan.py`, `GmOrb.tsx` |
| Trade History / Outcomes | **Live** (W, M) | `/v1/trade-outcomes/history`, `web-next/src/app/trade-history` |
| "Did this trade happen?" prompt | **Live on mobile only.** The caller's brief said it doesn't exist; it does. `mobile/src/components/TradeOutcomePrompt.tsx` is mounted at the root and calls `/v1/trade-outcomes/pending` on launch and on foreground. **Web never calls the pending endpoint**, so web users never get asked. | `RootNavigator.tsx:257`, `services/mobile_api_service.py:5207` |
| Beginner/advanced onboarding copy | **Live** (#1322) | |
| Live Draft | **Live on web, labelled "Coming soon"**, unverified against a real draft | `web-next/src/app/live-draft` |
| Referrals | **Live** | `/v1/referrals/my-code` |
| GM Targets | **Live** (3 free / 50 Pro) | |
| League Recaps (weekly stories, transaction timeline) | **Live** | `/v1/leagues/{id}/recap`, `/history` |
| Guess the Player + "Who is who?" + league leaderboard | **Live** | `/v1/guess-the-player*`, `guess_the_player_streaks` tables |
| League Pulse, team streak badges | **Live** | `modules/manager_activity.py`, `modules/team_streaks.py` |
| Push notifications | **Mobile only**, cron sweep over Next Moves | `modules/push_triggers.py` |
| Decision Memory | **Backend + legacy Streamlit.** Tables exist (`decision_memory_events`, `decision_memory_baselines`). Mobile has a device-local "since last check-in" diff instead (`mobile/src/lib/sinceLastCheckIn.ts`). No web-next surface. | `modules/decision_memory.py` |
| Manager Tendencies | **Being built now** (backend). Today only a comment referencing Streamlit's `_classify_manager_tendencies`. | `services/mobile_api_service.py:1992` |
| Weekly GM Report | **Streamlit only** (`modules/weekly_report_ui.py`, `app.py:22683`). No API route. | |
| Recommendation feedback ("Not interested" etc.) | **Streamlit only** (`modules/feedback_ui.py`, used by `trade_hub_ui.py`). No API route. | |
| League history intelligence | **Partial.** `modules/league_history.py` normalizes transactions and explicitly does no analysis ("no winner/loser labels"). | |
| Season Review / GM Report Card | **Does not exist** | |
| Achievements/badges for users | **Does not exist.** `team_badges.py` labels teams and `player_awards.py` shows real NFL awards; neither rewards the user. | |
| Pick'em / predictions | **Does not exist** | |

Engines the ideas below reuse:

- `modules/playoff_simulator.py`: vectorized Monte Carlo (3,000 trials by
  default) over the real remaining Sleeper schedule. Team strength is
  **Roster Power only**, through one logistic slope fit by maximum likelihood
  on the league's own completed games (default slope 1.0 before enough
  games). It does **not** simulate player points. Its docstring says
  per-player season projection passes were judged too heavy for the server.
- `modules/matchup_win_probability.py`: one week, one matchup. Each starter
  is Normal(`point_estimate`, (high - low) / 2), the team total is the sum,
  and win probability uses the closed-form normal difference. **This is the
  right per-week model for a simulator**, not the season-level logistic.
- `modules/player_projections.py`: weekly projection from a recency-weighted
  trend, opponent defense and QB quality, with a stdev band. It returns
  `insufficient_player_data` for players with no recent games (rookies, week
  1), and never fabricates a number.
- `modules/weekly_box_scores.py` + `modules/sleeper.cached_season_player_weekly`:
  real per-week stat lines and fantasy points (PPR/half/standard), weeks
  1-18, by season.
- `modules/draft_assistant.py`, `modules/live_draft.py`: draft pools, roster
  needs, recommendation buckets, snake order maths.
- `modules/trade_hub_engine.py`, `modules/faab.py`, `modules/roster_needs.py`,
  `modules/rankings.py`: values, fit, FAAB guidance.
- `modules/league_recaps.py` (`build_matchup_history_rows`),
  `modules/share_card_renderer.py` (branded PNGs).

**What we don't have, and must not pretend to have:** live play-by-play or
in-game events, real injury probabilities, snap-level data, or preseason
projections for rookies. Anything below that needs these says so.

---

## 1. Season simulator

### 1.1 The pitch

"Play a fantasy season in 15 minutes." Draft a team (or bring your real one),
then play week by week: set a lineup, bid on waivers, take or make trades,
deal with injuries, and see how your season ends. It fills the dead months
(January to August) when a dynasty manager has nothing to do in their real
league, and it doubles as the **mock draft simulator the competitor audit
says we lack** (audit 3.4, gap 3).

Dynasty Scout lists a "season simulator" (audit section 2) but we couldn't
test it, so we have no read on its depth.

### 1.2 Modes

| Mode | What it is | Data it needs | Phase |
|---|---|---|---|
| **Quick Draft (single season)** | Fresh 10 or 12-team league, you vs AI. Snake draft, then a full regular season and playoffs. | Player season table (1.4) | MVP |
| **My League (single season)** | Import your real Sleeper league: your real roster, your league-mates' real rosters run by AI, your real scoring and roster slots. "What happens if I make this trade?" played out over a whole season. | Rosters and settings we already fetch | Phase 2 |
| **Rest of Real Season** | Same as My League but starts from this week's real standings and real remaining Sleeper schedule. A hands-on version of Playoff Odds. | Above + `league_standings` + remaining matchups | Phase 2 (in season only) |
| **Replay a past season** | Draft, then play against **real 2025 weekly box scores**. No randomness for player points: every score is a real score. Honest, cheap and fun ("could you have won 2025?"). Hindsight bias is the catch, so hide future weeks and only reveal each week's real lines after you lock. | `cached_season_player_weekly(pid, 2025)` | Phase 2 |
| **Dynasty (multi-season)** | Keep your team across seasons: aging, a rookie draft, cuts. | An aging curve and rookie projections we don't have yet | Phase 4, and only if Phase 1-3 retention justifies it |

**Recommendation:** single season first. Multi-season dynasty is the
on-brand mode, but it needs player development modelling we don't have.
Inventing it would break the "no fabricated data" rule unless it is clearly
labelled as a game model.

### 1.3 The weekly loop

Each simmed week is one screen with four short steps. A "Sim to end" button
auto-plays the rest with AI defaults for impatient users.

1. **News and injuries.** 0-2 injury events across the league, drawn from
   the injury model (1.5). Your injured starters are flagged.
2. **Waivers.** Free agents ranked by the same need-aware logic as the real
   Waivers page. MVP uses rolling priority (reverse standings). Phase 2 adds
   blind FAAB: you bid, AI bids by need × value (reusing `faab.py`'s
   guidance bands), ties go to waiver order.
3. **Trades.** 0-2 incoming AI offers per week, plus a "propose a trade"
   sheet. AI acceptance rules in 1.6. Phase 2.
4. **Lineup.** Auto-filled with the best projected lineup (as `/my-team`
   does). The user can swap. Lock → the week resolves → box score, standings
   and updated playoff odds.

Playoffs use the league's bracket size. In My League mode that is the real
`playoff_teams` setting, as `league_standings` reads it.

### 1.4 How a simmed week is generated

Per player, a static row computed server-side once a day:

| Field | Source |
|---|---|
| `mean_ppg` by scoring format | Blend of the current season's recency-weighted trend (`player_projections`) and last season's per-game average (`cached_season_player_weekly`), weighted by games played |
| `sd_ppg` | Real per-player weekly stdev, already computed in `_player_recent_trend`; widened for small samples as `_band_half_width` does |
| `bye_week`, `team`, `pos`, `age` | Schedule and Sleeper directory |
| `value`, `ovr` | `rankings.py` (for drafting and trading) |
| `miss_rate` | Position-level weekly injury rate (1.5) |
| `est` flag | True when `mean_ppg` is estimated (rookies, no games) |

Rookies and players with no games get a **position + value-tier baseline**:
last season's average PPG for players at the same position and value rank.
The UI marks these as "estimated" the same way the rest of the app marks
low-confidence numbers. This is the one place the sim must estimate, and
it should say so.

Each simmed week, per starter: `points = max(0, Normal(mean_ppg, sd_ppg))`.
Team total = sum. Higher total wins. This is exactly the model
`matchup_win_probability.py` already uses for its odds, so the sim's own
"projected to win" bar and its outcomes agree. A small shared weekly
"game-script" factor per NFL team (QB and WR on the same team move together)
is a nice Phase 3 touch that would make stacks matter. Leave it out of the
MVP.

What we reuse from `playoff_simulator`: the vectorized-trials approach and
the tiebreak order (wins, win %, points for, points against, name) for the
standings. The in-sim playoff odds after each week can call the same
logistic model fed with the simmed records, or simply run 500 quick
point-level trials client-side. What we **don't** reuse is Roster Power as
the strength signal: a game needs real point totals to show.

**Calibration check (Phase 0):** sim the 2025 season 1,000 times from real
week-1 rosters and compare the spread of team totals and records against
what really happened. If the sim's score spread is too narrow, scale `sd_ppg`.
This is a one-off script, not a product feature.

### 1.5 Injuries

We have no injury-probability model and should not pretend to. A simple,
labelled game model is fine:

- Weekly injury chance per position, measured from last season's data as
  "rostered player with no stat line in a week his team played". This mixes
  injuries with benchings and healthy scratches. Say so in the methodology
  note, and cap it at plausible ranges (roughly 4-7% per week).
- Duration: 1 week (50%), 2-3 weeks (35%), 4-8 weeks (15%). This is a
  stylized choice, not a measured one, and is labelled as such.
- Real injury status at the time of import (Out/IR) is honoured in My League
  mode, because we already have it.

### 1.6 How AI managers decide

All of these are pure functions over the static player table, so they can
run client-side.

- **Draft:** value-based board (`value` + positional need from roster slots),
  with ±10% noise per manager so drafts differ, a positional cap (no 4th QB
  in 1QB), and a 2-3 round "reach" chance for flavour. Reuses
  `draft_assistant`'s buckets (Best Value, Best Fit) as the scoring idea, not
  the code (that code is pandas on the server).
- **Lineup:** best projected lineup, always. AI doesn't make lineup mistakes
  in MVP. "Lazy manager" difficulty can add some later.
- **Waivers:** claim if a free agent's `mean_ppg` beats the AI's worst
  rostered player at a position of need by a threshold. FAAB bid =
  need × value band from `faab.py`.
- **Trades:** accept if received value ≥ given value × (1 + margin) and the
  trade doesn't break the AI's starting lineup. Margin depends on persona:
  **Contender** (values `mean_ppg`), **Rebuilder** (values youth and
  `value`), **Balanced**. In My League mode, personas could come from the
  **Manager Tendencies** backend once it ships (real league behaviour). That
  is a strong tie-in: the sim behaves like your real league-mates. Until
  then, personas are assigned from Roster Power rank (top third Contender,
  bottom third Rebuilder), the same thirds idea `team_badges` uses.
- **Incoming offers:** each week, 1-2 AI teams with a need you can fill
  generate a 1-for-1 or 2-for-1 offer near fair value. This is the
  Trade Hub idea in miniature.

### 1.7 Reusable vs new

| Piece | Reuse | New |
|---|---|---|
| Player values, OVR, positions, byes | `rankings.py`, schedule | Daily export job |
| Weekly mean/stdev | `player_projections`, `cached_season_player_weekly` | Blend + rookie baseline |
| Week resolution maths | `matchup_win_probability` model | TS port (about 30 lines) |
| Standings and tiebreaks | `playoff_simulator._tiebreak_rank` logic | TS port |
| Real league import | Existing roster, settings and standings fetches | Thin endpoint that bundles them |
| Real past box scores | `weekly_box_scores`, season cache | Export per season |
| Draft UI | Live Draft board pieces on web | New simulator draft room |
| Share card | `share_card_renderer.py` | New card layout |
| Leaderboard | Guess the Player league leaderboard pattern | New table |
| AI managers, injuries, sim engine, weekly UI | | **All new** |

Most of the work is new UI and a new client-side engine. The data side is
mostly reuse.

### 1.8 Server cost (the owner wants this low)

**Run the simulation on the client.** The server ships one static data
bundle, and the browser or phone does every draw.

- **Data bundle:** about 600 fantasy-relevant players × about 12 fields ≈
  100-150 KB JSON, roughly 25-40 KB gzipped. One file per scoring format
  (3 files), rebuilt once a day by a batch job (seconds of CPU per day in
  total). Served with long cache headers, so most requests never reach the
  Python workers. Past-season replay is one more static file per season.
- **CPU per simmed season, client-side:** 12 teams × 17 weeks × about 9
  starters ≈ 1,800 normal draws, plus AI waiver and trade checks (about 12
  teams × 300 free agents × 17 weeks ≈ 60K comparisons) and a 500-trial odds
  refresh per week. Estimate: **well under 100 ms of JavaScript on a
  mid-range phone for a whole season.** That is an estimate, not a
  benchmark; Phase 0 should time it.
- **Same thing server-side in Python/numpy** would be roughly 50-200 ms per
  season. That would be fine at low volume but is wasted money compared with
  doing it on the client.
- **Per-user server cost:** a My League import is one request that reuses
  already cached roster/settings fetches. Finishing a season writes one small
  row (score, record, seed) for leaderboards and stats. Per season simmed:
  **about 0 CPU and one database write.**
- **What not to do:** don't run AI trade evaluation through the real
  `trade_hub_engine` per simmed week on the server. That is the expensive
  path `playoff_simulator`'s docstring already warned about.

Code sharing: web and mobile are separate apps with no shared TS package
today. Write the engine as a dependency-free TypeScript module with its own
unit tests, and vendor the same file into `web-next/src/lib/sim/` and
`mobile/src/lib/sim/` with a CI check that the two copies match. A shared
workspace package would be cleaner but is a larger repo change.

### 1.9 Session length and replay value

- Draft: 4-8 minutes (12 rounds × ~20 s per user pick; AI picks are
  instant). "Auto-draft" for the impatient.
- Regular season: 30-60 s per week when engaged; 14 weeks ≈ 10 minutes.
  "Sim to end" finishes it in one tap.
- **Total: 15-20 minutes per season**, and it can be paused and resumed
  (state saved in local storage on web and AsyncStorage on mobile; a run is
  small).

Replay hooks:

- New seed every run; difficulty (AI trade margin, lineup errors).
- **Daily seeded challenge:** everyone gets the same seed, draft slot and
  league that day, so scores are comparable. This is what makes a
  leaderboard fair, and it creates a daily reason to return (like Guess the
  Player).
- Challenge presets: "Win from the 12th pick", "No QB before round 8",
  "Rebuild: start with the worst roster".
- Personal stats: championships, best record, best draft grade.

### 1.10 Social hooks

- **League-mate leaderboard** for the daily seed and for My League runs,
  reusing the Guess the Player league leaderboard pattern
  (`/v1/leagues/{id}/guess-the-player/leaderboard`).
- **Shareable result card:** final record, title or not, MVP player, draft
  grade, rendered by `share_card_renderer.py` (already used for Trade Hub
  share cards). The card should say "Simulated season" so nobody mistakes it
  for a real result.
- **"Beat my sim" link:** share a seed so a friend plays the same league.
  Pure client-side; the seed is in the URL.

### 1.11 Free vs Pro

Server cost is near zero, so the free tier can be generous. The paid line
should follow what's personal, not what's expensive.

| | Free | Pro |
|---|---|---|
| Quick Draft single season | Unlimited | Unlimited |
| Daily seeded challenge + leaderboard | Yes | Yes |
| Replay a past season | 1 per week | Unlimited |
| **My League / Rest of Real Season** | 1 run per week | Unlimited, plus "what if" trade runs from Trade Analyzer |
| Dynasty multi-season (later) | No | Yes |

The strongest conversion moment: **"Run this trade through the season sim"**
from the Trade Analyzer, showing championship odds with and without the
trade. That ties the game to the core product. It is a Pro hook, and it is
cheap if it runs client-side (FantasyCalc already offers post-trade playoff
odds, audit section 2, so a plain version is table stakes).

### 1.12 Phased plan

Effort is for one engineer agent working in this repo, rough.

| Phase | Scope | Effort |
|---|---|---|
| 0. Spike | Daily player-bundle export endpoint; TS engine for week resolution and standings; 2025 calibration script; time a season on a phone | 2-3 days |
| 1. MVP (web) | Quick Draft single season: snake draft vs AI, weekly lineup, rolling-priority waivers, injuries, playoffs, end screen and share card. No trades. Lives inside a Games hub (section 4). | ~2 weeks |
| 2. Depth | My League import, Rest of Real Season, FAAB, AI trade offers and user proposals, Replay a past season, local save/resume | ~1.5-2 weeks |
| 3. Mobile + social | Mobile port of the engine and UI, daily seeded challenge, league leaderboard, "beat my sim" links, "Run this trade through the sim" from Trade Analyzer | ~1.5-2 weeks |
| 4. Dynasty multi-season | Aging, rookie draft class, multi-year saves. Needs a documented aging curve. | ~2-3 weeks, only if Phase 1-3 data says users come back for it |

**MVP total: about 2.5 weeks for web, about 6 weeks for the full
single-season experience on both platforms.**

---

## 2. Other engagement ideas

Effort: XS < 1 day, S 1-3 days, M 1-2 weeks, L 2+ weeks. Server load:
**None** (client or static), **Low** (one cached read or a weekly batch),
**Med** (new per-user server compute on a schedule).

| Idea | What it is | Why users come back | Reuse / effort | Server load |
|---|---|---|---|---|
| **Weekly challenges and streaks** | One small task per week ("Set your lineup before Sunday", "Answer 5 Guess the Player days", "Check your matchup"), with a streak counter. | Habit loop; streaks are already proven by Guess the Player. | Reuse `guess_the_player_streaks` pattern and Next Moves; S | Low |
| **Pick'em / predictions** | Before each week, pick the winner of every matchup in *your own* league (plus an optional "upset of the week" or "top scorer"). Scored against real Sleeper results. Season-long league leaderboard. | Every week has a reason to open the app twice: to pick and to check. Uses your league, which no generic pick'em does. | Matchup pairings and results already fetched (`league_recaps`), leaderboard pattern exists; M (S for picks-only) | Low: one scoring batch per league per week after games finish |
| **League rivalry and head-to-head** | All-time record between you and each league-mate, biggest blowout, closest game, current streak; a "Rivalry week" callout when you play your worst head-to-head opponent. | Personal and social; trash-talk fuel. | `build_matchup_history_rows` and `league_history_window` already walk past seasons; S | Low (cached history) |
| **Season Review / GM Report Card** | End-of-season personal report: record vs projected, best and worst moves, trades graded with Trade Outcomes, waiver hits, lineup efficiency (points left on bench), roster value change, and how you did vs our recommendations. Shareable "Wrapped"-style card. | A season-end ritual, very shareable, and a reason to come back in December. Closes the "Wrapped" gap in the audit (3.5, gap 10). | Recaps, transaction grades, trade outcomes, box scores, share cards; M | Low: computed once per user per season, cached |
| **"Did this trade happen?" on web** | Port the mobile prompt to web (same `/pending` and `/answer` endpoints). | Without answers, Trade Outcomes, the Report Card and Decision Memory have nothing to grade. | Endpoints exist; XS-S | None (one cached read on load) |
| **Weekly GM Report notification** | Tuesday push (mobile) and Dashboard card (web): last week's result, lineup points left on bench, top waiver for your needs, one trade idea, playoff odds move. | A predictable weekly touchpoint. | Streamlit `weekly_report_ui` content, recaps, matchup, waivers, playoff odds; needs an API route; M | Low-Med: one per-user build per week; reuse cached pieces, run in the existing push cron |
| **Achievements/badges** | Earned, personal badges: "First trade logged", "Sold high", "Waiver wizard" (a pickup became a starter), "Perfect lineup", "Sim champion", Guess the Player streaks. Shown on one profile strip. | Collection and status. Weak alone; strong as the reward layer for everything else. | Real data only (box scores, outcomes, streaks); S-M | Low (evaluated on events or in weekly batch) |
| **Share moments** | Prompt a share card at peak moments only: big win, trade graded A, title, sim championship, Report Card. | Growth more than retention; each share is an invite. | `share_card_renderer` + referral code on the card; S per moment | Low (PNG render on demand; cache) |
| **Recommendation feedback** (roadmap B) | "Not interested / Unrealistic / Already tried / Good" on Trade Hub, Waivers and Next Moves cards. | Recommendations stop repeating rejected ideas, so the app feels like it learns. | Streamlit `feedback_ui` exists; needs API + table + filter; S-M | Low |
| **Decision Memory 2.0 on web** (roadmap) | "Since your last visit": what changed in your recommendations and why. | Continuity between visits. | Tables and module exist; web surface missing; mobile is device-local; M | Low |
| **Durable alerts read state** (roadmap) | Read on phone = read on web. | Quality of life. | `mobile_alert_reads` / `notification_read_state` tables exist; verify both clients use them; XS-S | None |
| **Manager Tendencies surface** (roadmap A) | Manager profile backed by real transactions ("rarely trades firsts"). | Trade prep; also feeds sim personas and trade realism. | Backend in progress; S-M for the UI | Low (cached per league) |
| **League history intelligence** (roadmap D) | Contenders vs perpetual rebuilders, draft hit rates over seasons. | Depth for engaged leagues. | `league_history` normalizes only; analysis is new; M-L | Low |
| **Player accolades** (roadmap C) | Real NFL awards as badges in Player Quick View. | Polish, not a return driver. | `player_awards.py` + `AwardsStrip.tsx` already exist; mostly done | None |
| **Start/sit for your matchup, with bulk across leagues** (audit gap 5) | Compare two players for this week, with the projection band. | Every Sunday morning. | `player_projections`, `/my-team`; S-M | Low |
| **Player-exposure Portfolio** (audit gap 2) | Shares of each player across your leagues. | Multi-league users check it whenever news breaks. | `/v1/portfolio` already fetches rosters; S-M | Low |
| **Raise the free league cap 1 → 2-3** (audit gap 4) | Config change. | Users with 2+ leagues stop leaving for free tools. | XS | Low |
| **Lineup-lock reminder push** | "You start an injured/bye player" push Saturday night and Sunday morning. | Saves users a loss; trust. | Push cron + injury status + roster slots; S | Low |

Ideas considered and **not** recommended now:

- **Live in-game tracking.** We have no play-by-play feed. Sleeper's own app
  does this better. Our "live" win probability only updates when the stats
  cache refreshes.
- **Public chat or forums.** Sleeper chat is loved (audit section 2);
  competing with it adds moderation cost and clutter.
- **Paid contests or anything betting-like.** Legal and App Store risk for
  little gain.
- **Daily trivia beyond Guess the Player.** Two games already exist; a
  third quiz dilutes them. Put the effort into the sim's daily seed instead.

---

## 3. Ranked list and recommended order

Engagement impact is about weekly returning users. "Status" is from section 0:
**live** = shipped on web and/or mobile, **backend-only** = backend or
Streamlit only, **new** = not built. Roadmap = from the owner's PDF.

| Rank | Idea | Status | Roadmap? | Engagement impact | Effort | Server cost |
|---|---|---|---|---|---|---|
| 1 | "Did this trade happen?" on web | live (mobile only) | Yes (Trade Outcomes) | Medium, but it unlocks 4, 6, 9 | XS-S | None |
| 2 | Weekly GM Report (push + Dashboard card) | backend-only (Streamlit) | Yes | High (weekly touchpoint) | M | Low-Med |
| 3 | Pick'em on your own league | new | No | High in season | M | Low |
| 4 | Season Review / GM Report Card | new | Yes ("one additional idea") | High (season end + sharing) | M | Low |
| 5 | Season simulator (Phases 0-1) | new | No | High in offseason; Medium in season | M-L (2.5 wk MVP) | None-Low (client-side) |
| 6 | League rivalry / head-to-head | new (data exists) | Partly (league history) | Medium | S | Low |
| 7 | Recommendation feedback | backend-only (Streamlit) | Yes (B) | Medium (trust, less repetition) | S-M | Low |
| 8 | Lineup-lock reminder push | new | No | Medium-High in season | S | Low |
| 9 | Achievements/badges | new | No | Low alone, Medium as a layer | S-M | Low |
| 10 | Decision Memory 2.0 on web | backend-only | Yes | Medium | M | Low |
| 11 | Manager Tendencies surface | backend in progress | Yes (A) | Medium (also improves sim and trades) | S-M after backend | Low |
| 12 | Weekly challenges and streaks | new (pattern exists) | No | Medium | S | Low |
| 13 | Share moments | partial (Trade Hub card) | Partly (referrals) | Low retention, good growth | S each | Low |
| 14 | Durable alerts read state | verify; tables exist | Yes | Low-Medium | XS-S | None |
| 15 | Start/sit tool | partial (matchup lineup) | No | Medium in season | S-M | Low |
| 16 | Player-exposure Portfolio | new | No (audit gap 2) | Medium for multi-league users | S-M | Low |
| 17 | League history intelligence | backend-only (normalize only) | Yes (D) | Low-Medium | M-L | Low |
| 18 | Season sim Phases 2-3 (My League, mobile, daily seed) | new | No | High once MVP proves out | ~3.5 wk | None-Low |
| 19 | Player accolades | live (`AwardsStrip`) | Yes (C) | Low | Done | None |
| 20 | GM Plan / Orb, Live Draft, referrals, onboarding, GM Targets | live | Yes | (maintain) | — | — |
| — | Season sim Phase 4 (dynasty multi-season) | new | No | Unknown | L | None-Low |

### Recommended order, next ~6 weeks (2026-10-22 to 2026-12-02)

Timing matters. It is NFL week 8. Fantasy playoffs run roughly weeks 15-17
(mid to late December). In-season loops pay off now. The simulator pays off
in January-August, so it should be ready by the end of the fantasy season,
not rushed into mid-season.

| Week | Ship | Why now |
|---|---|---|
| 1 | "Did this trade happen?" on web (1); lineup-lock reminder push (8) | Cheap. Starts collecting outcome answers the Report Card needs in 6 weeks. |
| 2-3 | Weekly GM Report (2); Pick'em on your league (3), picks-only version first | Ten regular-season weeks are still left to run both loops. |
| 3 | League rivalry / H2H (6) inside Matchup | Small, uses existing history; pairs with Pick'em. |
| 3-6 | Season sim Phase 0 spike, then Phase 1 web MVP (5) | Ready for the offseason; beta it to Pro users in December. |
| 5-6 | Season Review / GM Report Card (4) | Must be ready when leagues finish in late December. Launch per league when its season completes. |
| Fill-in | Recommendation feedback (7) once Manager Tendencies ships | Both improve trade realism. |

After the window: sim Phases 2-3 in January, Decision Memory 2.0 on web,
Achievements as the reward layer across sim, Pick'em and Report Card.

---

## 4. Clutter guardrails

The web sidebar already has **18 entries** (`web-next/src/lib/navDestinations.ts`:
Dashboard, Alerts, My Team, Matchup, Waivers, Players, League Rankings, Trade
Hub, GM Plan, Draft Center, Live Draft, League Recaps, Home, Portfolio, News,
Trade History, College Scouting, Community). Guess the Player has no nav
entry; it lives as a Dashboard card (web) and a popup (mobile).

Rules:

1. **At most one new nav entry from this whole doc: "Games".** It holds the
   season simulator, Guess the Player, "Who is who?", Pick'em and their
   leaderboards. The existing `/guess-the-player-leaderboard/[leagueId]`
   route moves under it. The Dashboard keeps one small Games card, not one
   card per game.
2. Everything else goes into an existing surface or into the GM Orb's action
   list (3-5 items, per the roadmap's "Alerts = what changed, Orb = what
   should I do next").
3. Prompts (trade follow-up, Report Card ready, Pick'em open) use the
   existing root-level prompt pattern (`TradeOutcomePrompt`,
   `GuessThePlayerPrompt`) and show **one at a time**, at most one per
   session.
4. Pushes respect existing per-category toggles; a new category for each new
   push type, default off for anything promotional.
5. Reuse the shared components and tokens (standing UI-consistency rule):
   share cards, leaderboard tables, badges. No per-page variants.
6. Consider retiring or folding one entry when Games is added. Candidates:
   College Scouting (empty catalog, audit 4.1) moves under Draft Center, and
   Live Draft becomes a tab of Draft Center. That makes Games net-negative
   on nav count.

| Idea | Where it lives | New nav entry? |
|---|---|---|
| Season simulator | Games hub; entry point also from Draft Center ("Mock a season") and Trade Analyzer ("Run through the sim") | **Yes: Games** (shared) |
| Pick'em | Games hub + a card on Matchup during the week | Shared Games entry |
| Weekly challenges / streaks | Dashboard card and Games hub header | No |
| League rivalry / H2H | Matchup page section; League Recaps | No |
| Season Review / Report Card | League Recaps (season tab) + one-time prompt + Orb item | No |
| "Did this trade happen?" (web) | Root-level prompt, as on mobile; answers in Trade History | No |
| Weekly GM Report | Push (mobile) + Dashboard card (web); archive in League Recaps | No |
| Achievements | One strip on the Account/profile page; badge toast on earn | No |
| Share moments | Share button on the existing result surfaces | No |
| Recommendation feedback | Overflow menu on existing recommendation cards | No |
| Decision Memory 2.0 | Dashboard "Since your last visit" section | No |
| Manager Tendencies | Manager profile sheet from League Rankings / Trade Hub partner cards | No |
| League history intelligence | League Recaps | No |
| Lineup-lock reminder | Push + Orb item | No |
| Start/sit | Matchup page | No |
| Player exposure | Portfolio page | No |

---

## 5. Open product questions for the owner

1. **Games nav entry.** OK to add one "Games" hub (sim, Guess the Player,
   Pick'em), and to fold College Scouting and Live Draft into Draft Center
   to keep the nav count flat?
2. **Simulator scope.** Single season first (recommended), or is dynasty
   multi-season the must-have? The latter needs an aging model we'd have to
   invent and label as a game model.
3. **Estimated numbers in the sim.** The sim needs estimated points for
   rookies and a stylized injury model. Is a clear "simulated / estimated"
   label acceptable under the no-fabrication rule, given it's a game?
4. **Free vs Pro split for the sim.** Is "My League" mode the Pro hook (1
   free run a week), or should the whole sim be free as a top-of-funnel
   game?
5. **Timing.** Build the sim now for an offseason launch, or push it behind
   the in-season loops (Weekly Report, Pick'em, Report Card)? This doc
   recommends running them in parallel and launching the sim in December.
6. **Pick'em scope.** Own-league matchups only (recommended), or also NFL
   games? NFL pick'em needs an odds/results feed we only partly have (Vegas
   lines exist on player schedules) and invites betting comparisons.
7. **Notifications budget.** How many pushes per week is acceptable?
   Weekly Report + lineup reminder + Pick'em open could mean 3 a week on top
   of today's Next Moves pushes. Sleeper users already complain about too
   many notifications (audit section 2).
8. **Report Card honesty.** Grading users against our own recommendations
   can make us look bad when we were wrong. Show that anyway? (Recommended:
   yes, it builds trust.)
9. **Web push.** Web has no notifications today. Is the Weekly Report on web
   a Dashboard card only, or do we add email?
