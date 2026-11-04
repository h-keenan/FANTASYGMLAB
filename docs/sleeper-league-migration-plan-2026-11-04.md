# Sleeper league migration: plan (2026-11-04)

Request (coridian_): "seamless import/migration of people's leagues from Sleeper to
our platform when we're all set up for it. As far as I know we get all the info we
need from the API." Docs only; no code changes. Sleeper API facts come from
https://docs.sleeper.com (fetched 2026-11-03) and our adapters. Anything not
confirmed is marked UNVERIFIED. Not legal advice.

## TLDR

- The API covers almost all HISTORICAL and CONFIG data for a league. It does not
  cover accounts, auth, chat, or anything private, and it is read-only.
- Today we are a read-only companion. Hosting a league natively (lineups, waivers,
  trades, drafts, live scoring, commissioner tools, payments) does not exist and is
  a months-long product, not an import feature.
- The docs say the API is free for NON-COMMERCIAL use and that commercial use needs a
  license from Sleeper. We have paid tiers. Resolve this before anything else.
- Recommended next step: ship Phase 1 (read-only league record + history), after the
  owner settles the licensing and product-scope questions in section 6.

## 1. What the Sleeper API gives us vs not

Base URL `https://api.sleeper.app/v1`. Adapters: `modules/sleeper.py` (league data,
cached, budgeted via `modules/sleeper_budget.py`), `modules/sleeper_leagues.py`
(user to leagues, season rollover). NFL only for leagues and drafts per the docs.

| Native-league need | API covers? | Where we read it today |
|---|---|---|
| League settings (playoff start week, roster/waiver settings, trade deadline, etc.) | Yes, `GET /league/{id}` `settings` (field-level docs are thin; we read specific keys) | `sleeper.get_league`; `modules/faab.py` (waiver_budget, waiver type) |
| Scoring settings | Yes, `scoring_settings` (key/value map; docs give no field list, so unknown keys must be handled defensively) | `modules/league_value_settings.py`, `modules/idp_scoring.py` (consumers) |
| Roster positions / slots | Yes, `roster_positions` | same |
| Users (names, avatars, team names) | Yes, `/league/{id}/users`. Public profile only | `sleeper.get_users`, `get_league_roster_profiles` |
| Rosters (players, starters, reserve, taxi, record, points, waiver position, FAAB used) | Yes, `/league/{id}/rosters` | `sleeper.get_rosters` |
| Roster-to-user mapping | Yes (`owner_id`, `co_owners`) | `sleeper.get_user_roster_id` |
| Drafts and picks | Yes: `/league/{id}/drafts`, `/draft/{id}`, `/draft/{id}/picks` | `sleeper.get_league_drafts/get_draft/get_draft_picks` |
| Traded picks (future pick ownership) | Yes, `/league/{id}/traded_picks` | `sleeper.get_traded_picks` |
| Transactions: trades, waivers, free agents, with adds/drops/picks, week (`leg`) | Yes, per week `/league/{id}/transactions/{week}` | `sleeper.get_transactions` |
| FAAB bids | Yes per docs: `settings.waiver_bid` on transactions, `waiver_budget` for FAAB traded in trades | `modules/faab.py` |
| Failed/rejected claims and losing bids | UNVERIFIED. Docs list `status` on transactions; not confirmed that failed claims are returned with bid amounts | check `faab.py` first |
| Matchups per week (starters, points, per-player points) | Yes, `/league/{id}/matchups/{week}` | `sleeper.get_matchups`, `modules/weekly_box_scores.py` |
| Playoff brackets | Yes, winners and losers bracket endpoints | UNVERIFIED in our code: grep found no `winners_bracket` use |
| Season chain | Yes, `previous_league_id` | `modules/league_history.py`, `sleeper_leagues.resolve_current_season_league_id` |
| Player map and ids | Yes, ~5MB, docs ask for at most about once per day | `sleeper.get_players` (cached) |
| Trending adds/drops | Yes, attribution required | `sleeper.get_trending_players` |

NOT available (or not confirmed):
- Authentication and private data: no API token exists, and the API cannot modify
  anything. We cannot verify that the person importing is the commissioner. Username
  lookup is public, so anyone can name any league.
- Email addresses, phone, passwords, notification preferences, device tokens.
- League chat and DMs (no endpoint documented).
- Trade block, player notes, watchlists (no endpoint documented).
- Pending (unprocessed) trade proposals and pending waiver claims: only processed
  transactions appear as far as we know. UNVERIFIED.
- Commissioner-only content not in `settings` (rules text, constitution, dues info).
- Owner-uploaded logos exist only as CDN ids; they are user content (section 3).
- Non-NFL leagues.
- Anything deleted or hidden before our read; history is only what Sleeper still serves.

Consequence: "all the info we need" is true for config, rosters, picks, and history.
It is false for identity, permissions, communication, and anything forward-looking
(a native league needs its own versions of those).

## 2. What a native league would reuse vs build

Reusable today (read side):
- Player valuations, rankings, trade analysis and verdicts (`modules/trade_*`,
  `trade_grade.py`, `trade_hub_engine.py`).
- Sleeper adapters and caching/budget (`sleeper.py`, `sleeper_budget.py`), plus
  ESPN/Fleaflicker/MFL import adapters (`espn_leagues.py`, `fleaflicker_leagues.py`,
  `mfl_leagues.py`).
- League history and manager analytics (`league_history.py`, `manager_tendencies.py`,
  `manager_activity.py`), FAAB math (`faab.py`), waiver analysis (`waivers_logic.py`,
  recommendations only, does not process claims).
- Accounts: Supabase auth and `saved_leagues`/`profiles` (`docs/supabase_accounts.sql`,
  `modules/auth_supabase.py`, `account_store.py`).
- Push infra: `push_tokens.py`, `push_triggers.py`, `notification_center.py`
  (recommendation alerts, not league events).
- Payments: Stripe and RevenueCat for our subscriptions (`stripe_billing.py`,
  `revenuecat_billing.py`). That is app billing, not league dues.
- Commissioner view: `modules/league_integrity.py` is analysis only, with no powers.
- Draft: `live_draft.py`, `draft_assistant.py` read a live Sleeper draft and advise;
  they do not run a draft.

Missing entirely:
- Scoring engine that scores a week from raw NFL stats for arbitrary
  `scoring_settings` (today we read Sleeper's computed points).
- Live NFL stat/score feed with licensing for in-game updates (none in repo).
- Schedule generation (regular season, playoffs, consolation), tiebreakers, standings.
- Lineup submission, positional eligibility validation, per-game lineup locking.
- Waiver processing (priority, FAAB, claim order, run times, conflicts).
- Trade proposals, acceptance, veto/review periods, roster-limit enforcement.
- Draft room (real-time, timers, auto-pick, queues, pick trades, slow drafts).
- Commissioner powers (edit settings, force moves, invite/remove managers, disputes).
- League chat/messages and league notifications (lineup reminders, trade offers).
- Invite and membership model, ownership transfer, yearly league rollover.
- League dues/payouts (and the legal exposure that comes with them).
- Moderation/abuse tooling, support load, game-day uptime.

Honest size: hosting leagues is a full second product, on the order of months of
focused work plus ongoing game-day operational risk. Estimates below are rough
engineering guesses.

## 3. Legal and terms items to verify (owner/legal, no conclusions here)

1. Sleeper API terms. Docs say free for non-commercial use and commercial use needs
   a license from Sleeper. We charge for tiers. Confirm whether current use is
   covered, and whether a migration product aimed at Sleeper's users changes that.
   Get written permission before building on it.
2. Rate limits: docs say stay under 1,000 calls/minute or risk an IP block; our
   `sleeper_budget.py` assumes the same. Bulk history import multiplies calls;
   needs a queued, throttled importer.
3. Sleeper content: user names, avatars, team names, player images may carry their
   own rights. Do not copy CDN assets into our storage without review.
4. Player data and NFL stats licensing for a hosted product (names, headshots, team
   logos, live stats) differs from a companion app. See the pattern in
   `docs/advanced-stats-licensing-2026-11.md`. NFL/NFLPA marks need review.
5. Fantasy sports regulation: hosting leagues, especially with money (dues, prizes),
   may trigger state-by-state rules; age gating and terms for minors; free vs paid
   contests. Ask counsel.
6. Privacy: importing data about managers who have not signed up (GDPR/CCPA-style
   notice, deletion on request). See `docs/supabase_delete_account.sql`.
7. App Store / Google Play: user-generated content (chat) needs moderation and
   report/block features; paid contests have their own store rules.
8. Consent: a user can import a league they do not run. Decide whether the
   commissioner must approve, since the API cannot verify commissioner identity.

## 4. Phased path

Phase 0: snapshot and history for analytics (TODAY). Connect a league, read live,
cache. Effort: done. Decision: none.

Phase 1: one-click import into a FantasyDesk league record, read-only, with a
Sleeper link.
- Effort: about 2-4 weeks (schema, throttled importer, web and app UI per the
  web/app parity rule).
- Risks: Sleeper license (section 3), stale data vs Sleeper (Sleeper stays source
  of truth), history gaps, duplicate imports, rate budget.
- Owner decision: approve scope and licensing path; who may import (any user vs
  verified commissioner); whether non-members can be invited.

Phase 2: native lineups, waivers, trades.
- Effort: about 3-5 months (membership, rules engine, lineup lock, waiver run,
  trade flow, commissioner tools, notifications, support tooling).
- Risks: game-day correctness (a wrong lock or waiver run destroys trust), scoring
  accuracy, concurrent edits, abuse, support load.
- Owner decision: commit to being a league host (a second product); free-only vs
  money; stat/data provider; staffing.

Phase 3: native drafts and live scoring.
- Effort: about 3-6 months more (real-time draft infra, live stat feed, scoring engine).
- Risks: real-time scale spikes, stat feed cost/licensing, weekend on-call.
- Owner decision: stat provider and budget; full Sleeper alternative, or stay an
  intelligence layer that links out.

## 5. Phase 1 data model sketch (Supabase) and import UX

Applied by hand in the Supabase SQL Editor like other `docs/supabase_*.sql` files
(no migration runner). RLS: owner and league members read; writes by service role
only (import job). Names are proposals, not implemented.

- `fd_leagues`: id uuid, owner_user_id, source (`sleeper`), source_league_id,
  source_league_url, name, season, status, sport (`nfl`), settings jsonb,
  scoring_settings jsonb, roster_positions jsonb, previous_fd_league_id (chain),
  imported_at, last_synced_at, sync_state, UNIQUE(source, source_league_id).
- `fd_league_members`: league_id, fd_user_id (nullable until they join),
  source_user_id, display_name, avatar_ref, role (owner/commissioner/manager),
  invite_state, claimed_at.
- `fd_rosters`: league_id, source_roster_id, member_id, players jsonb, starters jsonb,
  reserve/taxi jsonb, wins/losses/ties, points_for/against, faab_used, waiver_position.
- `fd_drafts`, `fd_draft_picks`: metadata, order, per pick (round, slot, roster,
  player id, keeper flag); `fd_traded_picks` (season, round, original roster, owner).
- `fd_transactions`: league_id, season, week, type, status, adds/drops/picks jsonb,
  faab bid, created_at.
- `fd_matchups`: league_id, season, week, roster_id, matchup_id, points,
  starters jsonb, player_points jsonb; `fd_playoff_brackets` (shape UNVERIFIED).
- `fd_import_jobs`: id, league_id, status, progress cursor (season/week), error,
  api_calls_used, started/finished (throttling and retries).
- Keep Sleeper player ids as-is, map via the existing crosswalk, keep raw API JSON
  for audit and re-parse.

Import flow, 6 steps:
1. User picks a connected Sleeper league (already in `saved_leagues`).
2. We show what will be imported and that Sleeper remains the system of record.
3. User confirms and attests they are a member or the commissioner.
4. Background job walks the `previous_league_id` chain, throttled, with progress.
5. User reviews the summary (teams, seasons, picks, trades found; anything skipped).
6. Optional: user invites managers (share link) who claim their team; the league
   keeps an "Open in Sleeper" link.
User must: confirm the league, confirm authority, and send invites. We cannot do
that for them (the API has no email or contact data).

## 6. Recommendation and open questions

Next step: ask Sleeper about commercial use and this plan; in parallel build Phase 1
behind a flag, since it reuses data we already read and has no game-day risk.

Open questions for coridian_/Zach:
1. Do we have, or will we seek, a Sleeper commercial license? What if declined?
2. Goal: a Sleeper alternative (Phases 2-3) or the best intelligence layer?
3. Free leagues only, or dues/prizes (legal path differs a lot)?
4. Must the commissioner approve imports of a league?
5. Live stat/score data source and budget for Phase 3?
6. Who staffs game-day support if we host?
7. What do users want first: imported history, or native play?
