# Feature audit: what to refine and what to enhance (2026-10-27)

Asked by coridian_: "audit what features need to be refined or enhanced."
Priority lens: (a) the NFL trade-deadline advertising push (trades), (b) activation and retention, (c) premium conversion.

## Method and limits (read first)

- Code read from `origin/main` at `c6bbe397` (read-only worktree). Trade engine v2 (PR #1571, `origin/trade-engine-v2`, `docs/trade-engine-v2.md`) is OPEN and not merged; it is described as "pending", not as shipped.
- Builds on the earlier audits (web UX, onboarding, analytics, value, news, advertising, `docs/app-web-parity-audit.md`, `docs/dashboard-reorg.md`, `docs/live-activities-widgets-plan.md`). Several of their P0s have since shipped (forgot-password and landing copy #1554, Pro/Premium naming #1557, OAuth age gate and no onboarding replay #1558, referral capture and attribution #1547, analytics fixes #1555 and a follow-up, onboarding tiers #1556, Dashboard reorg #1570, public analyzer #1569, players.db refresh recovered: last 5 scheduled runs green, db refreshed today). Where an older finding is now fixed this doc says so.
- NOT verified: no simulator, device, browser, logged-in session or prod query was used. Grades for UI are code-derived. Live traffic numbers come from the analytics audit (7d: about 173 real visitors, 9 accounts, 1 checkout_started, 0 mobile events because mobile analytics are dark by policy). Nothing here measures conversion or retention directly.
- Grades: A solid, B good with gaps, C works but weak, D mostly a placeholder, F broken. Effort S under half a day, M up to 2 days, L more.

## Headline findings

1. The trade deadline is the campaign, and the product has no deadline mode beyond a Dashboard chip: no push, no deadline-aware ideas, no "last call" surface. `trade_window` exists server-side (`modules/league_calendar.py`) and is used by Dashboard, Trade Hub, Finder and GM Plan phase; `modules/push_triggers.py` has no deadline category.
2. The funnel the ads feed is leaky at the trade step. The public analyzer (`/trade-analyzer`, #1569) gives a value total only; the roster-aware verdict needs sign-up, league connect, and then free users get 3 evaluations a week (`trade_eval_usage.FREE_WEEKLY_TRADE_EVAL_LIMIT = 3`), 2 Trade Hub ideas (`FREE_VISIBLE_IDEAS = 2`) and no Trade Finder at all (`get_trade_finder_ideas` returns an upsell for non-Pro). The strongest differentiator is paywalled before the user trusts it.
3. Trust in trade verdicts is the product. The "-379 verdict that sold a Questionable RB" case drove engine v2 (#1571, open). Until it merges and is checked against real leagues, every share card and ad is exposed to a screenshot of a bad verdict. Value freshness also matters: the value audit showed values respond slowly to results (market about 44 percent of the composite) and injured stars keep 8-9k values.
4. Strong building blocks exist but are not tied together into a "closer" loop: counter-offer packages (`build_counter_offer_packages`), manager tendencies (`ManagerTendenciesCard`), partner archetype labels, trade outcomes/history, community feed, share-card PNG with QR. Missing: accept probability shown to the user, send-the-offer handoff, and what happened to the offer.
5. Web/app parity is good on core screens, with known gaps: no web Playoff Odds route, Teams/Roster/Pick detail are app-only, the app has no analytics (by policy) so iOS/Android funnels are invisible, Live Activities are scaffolded OFF.
6. Clutter: three trade tabs plus Hub/Finder/Analyzer/History/Community, Games (Guess the Player), Design route, Founder analytics inside the user app, News that is mostly generic headlines. See the cut/merge list.

## Feature inventory

Columns: what it does (verified in code), grade, parity (W web, A app), type (R refine, E enhance), top changes, impact, effort, dependencies, priority (D deadline push, A activation/retention, P premium).

### Trades (primary)

| Feature | What it does today | Grade | Parity | Type | Top 1-3 changes | Impact | Effort | Deps | Pri |
|---|---|---|---|---|---|---|---|---|---|
| Trade Analyzer, logged in (`TradeAnalyzerContent.tsx` 960 lines, `TradeAnalyzerScreen.tsx` 1156; `POST /v1/leagues/{id}/trade-analyzer`) | You pick assets and a partner; fit engine plus `decide_offer_verdict` returns accept/counter/fair/decline with bands, confidence, lineup delta, counter guidance, up to 3 counter packages, picks supported, keeper adjustment, share PNG with QR, "did this happen" record, community toggle. Free: 3 evals per week. | B (C until v2 merges) | Match (both carry counter, share, picks) | R first | 1) Merge and validate engine v2 (#1571): run it against 20 real leagues and a fixed set of regression screenshots before ads. 2) Replace "x of 3 left" hard stop with a deadline-week allowance (see deep dive). 3) Show the partner's likelihood to accept next to the verdict. | Highest: this is the ad landing | M | #1571 | D, P |
| Trade Analyzer, public (`/trade-analyzer`, `PublicTradeAnalyzer.tsx`, `/api/public-trade-values`) | Logged-out search of both sides, 1QB/SF/TEP, total and fair-trade verdict, share link `?a=&b=`, JSON-LD, FAQ, CTA to sign up or sample league. Neutral 12-team PPR values. | B- | Web only (app has no logged-out mode) | E | 1) Make the CTA a "see how this looks on YOUR roster" teaser with the real verdict blurred or summarized after connect. 2) Dynamic OG image per shared trade (static OG only today). 3) Add picks and a "who wins" headline that is shareable. | Top-of-funnel for the deadline push | M | OG image route | D, A |
| Trade Hub ideas (`TradeHubContent`, `TradeIdeaCard`, `TradeHubScreen`; `GET .../trade-hub`) | Generated, roster-aware ideas with give/get, fit, archetype labels, hold cards, strategy (contender/retool/rebuild), manager tendencies card, share card. Free sees 2; rewarded-ad unlock path exists for "all trades" (server-side capped). | B | Match; mobile has ad unlock | R+E | 1) Deadline ordering ("sell/buy before Wk N"), 2) show acceptance realism score (computed internally as `market_context.score`, never surfaced numerically), 3) one-tap "send in Sleeper" copy of the proposal text. | High | M | #1571 gate (`_UserSideAnalyzerGate`) | D, P |
| Trade Finder (`TradeFinderContent`, `TradeFinderScreen`; `GET .../trade-finder`) | Pick your players/picks to shop, finds partners who would want them; picks and "picks back" filter. Entire feature is Pro-only. | B | Match | E | 1) Give free users one search per week so the feature is seen. 2) Rename to "Shop a player" and link from every player row. 3) Add partner ranking by need and tendency, not just idea list. | Medium-high | S-M | none | P, D |
| Trade history and outcomes (`/trade-history`, `TradeOutcomePrompt`, `trade_outcome_results`, `trade-outcome-result-sweep` workflow, push "Did this trade happen?") | After a share, asks the user if it happened, later grades the result. Free. Pull-based page. | C+ | Match | E | 1) Show league-wide completed trades with our grade (a "trade desk" for the whole league) using `/history` and `all-trades`. 2) Feed outcomes back into verdict calibration (internal). 3) Win/loss tally on profile. | Retention and shareable | M | outcome volume (small today) | A |
| Community trades (`/community`, opt-in shared trades, reactions, report) | Opt-in feed of shared trades with reactions and reporting. | C | Web has page; app has `sharedTrades.ts` helpers | R | Decide: either seed it with the "interesting trades" external feed or fold into Trade Hub. Moderation/reporting exists; check volume before promoting. | Low now | S | volume | A |
| Counter-offer packages (`build_counter_offer_packages`) | 2-3 alternates, one or two asset changes, only returned if they regrade fair/accept; "Build the counter" applies it in the UI. | B+ | Match | E | Surface the best counter as a one-tap result on every non-accept verdict and in share text; v2 re-ranks by lineup points. | High | S | #1571 | D |
| Share cards for trades (`share_card_renderer.py`, `useShareImage`, mobile `TradeShareCard`) | Branded PNG with QR "Scan to try FantasyDesk", matched to in-app card (#1561). | B | Match (web client render, app native) | R | QR carries no `utm`/`ref` (advertising audit; verify after #1547). Add attribution and per-card OG landing. | Viral loop | S | none | D |

### Core league screens

| Feature | What it does today | Grade | Parity | Type | Top changes | Impact | Effort | Pri |
|---|---|---|---|---|---|---|---|---|
| Dashboard | Reorganized (#1570): Now strip (lineup, deadline chip, alerts, waivers), Trades block, Next moves, merged My Team, Watchlist, League Activity, collapsed More. Free sees 4 next moves. | B | Same order, shared constant + test | R | Visual QA at 390px never done; add deadline countdown card in last 2 weeks; confirm chip logic on a real league. | High | S | D, A |
| My Team | Snapshot, analysis, roster tabs, composition, keepers. | B | Aligned | R | Let each roster row open "shop this player" (Finder) and "trade value"; reduce duplicated metrics with Dashboard. | Medium | S | D |
| Waivers | Top target, more adds, position snapshot, free agent list, GM targets, FAAB. | B | Aligned | R | Check projections accuracy claims (value audit: our projections trail Sleeper, interval overconfident); label basis. | Medium | M | A |
| Matchup / win probability | Opponent, lineups, win probability, what-if (`matchup_win_probability.py`, `matchup_what_if.py`), recap. | B | Aligned | E | Live in-game updates need Phase 2 of live activity; add start/sit notes tied to injuries. | Medium | M | A |
| Playoff Odds | Simulator (`playoff_simulator.py`), app screen; no standalone web route (appears inside My Team/Rankings/GM Plan). | B- | Parity gap | E | Build a web route or record the exception; add "odds change from this trade" (best deadline hook). | High for trades | M | D |
| GM Plan | Phase-aware plan (including "Trade deadline approaching"), trade opportunities, targets. | B | Aligned | R | Dedupe with Dashboard Trades block (two places say the same thing). | Medium | S | D |
| GM orb | A navigation and search sheet on phone, sidebar on desktop. Not an AI assistant (no model call found in `GmOrb.tsx`). | C (as "assistant") | Name differs by device | R then E | Rename or explain ("Quick menu"); later add real questions answered from league data ("who should I sell?") routing to existing engines. | Medium (expectation gap) | S then L | A |
| Rankings / Values (`/dynasty-rankings`, `/dynasty-trade-value-chart`, `LeagueRankingsContent`, `PlayersContent`, `PlayerCompare`) | SEO pages (fast, JSON-LD, 317 sitemap URLs) plus in-app league rankings, players explorer, compare. FantasyCalc attributed. | B- | Aligned; compare app + web | R | Values are the trust base: in-season responsiveness (market 44 percent weight), injury discount, suffix-name matching for FantasyCalc (34 of top 200 without FC), cap value for teamless players. Add a "value as of" stamp and a stale-data banner. | Highest trust effect | M | D, P |
| Player pages (`PlayerQuickView`, `PlayerDetailScreen`, `/dynasty-players/[slug]`) | Quick view with value, tier, stats, news, contract bio; public SEO player pages. | B | Quick view vs detail hierarchy open | R | Add "trade value history" sparkline and "shop / target" buttons. | Medium | S | A |
| News (`NewsContent`, `AlertsContent`, `news-ingest` workflow) | RSS from 6 outlets plus structured Sleeper injury; ingest now scheduled (workflow green). Name-only identity matching, no transactions, no article-driven push. | C+ | Aligned | R | Roster-filtered alerts first; dedupe cross-outlet; source/time on every item; injury push already exists. | Medium | M | A |
| Draft Center / Live Draft (`DraftCenterContent`, `LiveDraftContent`, `live_draft_trade_evaluator`) | Draft board and live pick assistant with a trade evaluator. | B- | Aligned (both) | E | Offseason feature; park until August. Keep evaluator in sync with engine v2. | Low now | - | none |
| College scouting | Prospect list and detail, seed data. | C+ | Aligned | E | Offseason; only keep if draft capital is a pillar. | Low now | - | none |
| Portfolio / multi-league | Record, rank, needs across saved leagues; Pro; progressive loading. | B | Aligned | E | Cross-league "deadline checklist": which leagues still have a hot trade idea. | Medium (multi-league power users are the best advocates) | M | D, P |
| Games (Guess the Player) | Mini game, league leaderboard. | C | Aligned | cut/hide | Collapsed under More already; keep as engagement filler only. | Low | - | cut |

### Platform, growth and ops

| Feature | What it does today | Grade | Parity | Type | Top changes | Effort | Pri |
|---|---|---|---|---|---|---|---|
| Premium / paywall / billing (Stripe web, RevenueCat app; `/premium`; 3-day trial) | Free vs Pro comparison built from real limits, public pricing view now exists, trial, embedded checkout, billing portal. Only 1 `checkout_started` in 7d (analytics audit). | B- | Aligned; naming standardized | R | Move upsell to the moment of value (4th analyzer run, locked idea) with the specific blocked verdict; verify trial/card promise wording; track `checkout_completed`. | M | P |
| Notifications and push (`push_triggers.py`, `notification_center`) | Categories: top_priority, watch, recap, injury, lineup_lock, waiver_reminder, trade_followup, team_situation; weekly cap 4, quiet hours, per-category toggles. | B | App push; web alerts page | E | Add `trade_deadline` category (T-7, T-2, T-1 days) and "buy window" for contenders; reserve cap slots for it. | M | D |
| Share cards (player, compare, portfolio, recap, trade) | Shared by web client render and app native; external 1600x1600 card for the bot. | B | Match | R | Attribution on QR; dynamic OG for shared links. | S | D |
| Referral (`referrals.py`, ReferralCard) | Link `?ref=CODE`, 1 free month per N leaguemates who connect; capture fixed on web (#1547) and app (`referralCapture.ts`). | B- | Both; verify end to end | R | Run one real end-to-end redeem on web and app; promote at the end of a positive trade result. | S | A |
| Onboarding | Sign-in, carousel, optional paywall, Sleeper username; 3 tiers and goal (#1556); sample league and "Try a sample league" CTA. | B | Aligned; app flag is device-local | R | Order: value before paywall; sample league interactive (real analyzer on sample roster). | M | A |
| Settings / Account | Preferences, explanations level, notification settings, billing, referral, replay tour. | B | Aligned | R | Label drift (Beginner/Advanced vs onboarding names) was addressed in #1556; verify. | S | A |
| iOS Live Activities / widgets | Scaffolded, default OFF (`FANTASYDESK_LIVE_ACTIVITIES`), local-only updates, needs Apple portal work. | D (not usable) | iOS only | E | Not for the deadline. After Apple setup, deadline countdown widget is the best first use (not score). | L | later |
| External bot API (`/v1/external/*`) | Interesting trades feed, share card, news per player, player profiles, projections, recaps. | B | API | E | Add `since` news feed, deadline "hot trades" endpoint with attribution link. | M | D |
| Analytics (web-only by policy) | First-party events, founder page, bot filtering added. | B- | App dark | R | Add signup, paywall, checkout_completed, referral events; server kill-switch for mobile. | M | A, P |
| Marketing site / SEO | Landing is sample-first; SEO pages strong; apex `fantasygmlab.com` static page was stale in the earlier audit (verify now). | B- | n/a | R | Confirm apex now matches app landing and shows Play and App Store status. | S | D |
| Data pipelines | players.db refresh restored (5 consecutive green runs); `news-ingest` green; recent `Delivery Validation` runs failing (CI noise, per CLAUDE.md). | B- | n/a | R | Staleness alert on db age; guard `data/*.json` against test overwrites. | S | D |
| Founder analytics, Design route in app | Admin/dev surfaces shipped in the user bundle. | n/a | n/a | cut | Hide behind staff flag. | S | cut |

## Support-style walk-throughs (code-derived)

- Deadline-week user, free, mobile: opens Dashboard, sees a deadline chip and one trade idea. Taps Analyze, runs 3 trades, hits `weekly_limit_reached`. Cannot use Trade Finder. Gets no push about the deadline. Outcome: abandons or pays without having seen the best feature (counters). Fix: deadline allowance and a deadline push.
- Ad visitor: lands on `/trade-analyzer`, enters two players, sees a totals verdict, clicks CTA, creates an account, connects Sleeper, gets the real verdict. The public result is a neutral value total, so the roster-aware reason to switch is only described in text. Fix: show what the account adds with a concrete example from their own entry (e.g. "your RB room would be empty for 3 weeks").
- Rival sends an offer: the user can enter it in the Analyzer and gets a verdict and counters, but cannot paste Sleeper trade text or auto-import an incoming offer. Fix: pending-offer import (Sleeper trade proposals are not public; confirm API availability before promising).
- Shared card recipient: scans QR, lands on the bare product URL, not on the shared trade. Fix: link back to a public trade page with OG preview and the "analyze yours" CTA.

## Trade-feature deep dive: what would make us the best on the market

Current edge (verified): roster-aware lineup effect, league scoring (SF/TEP), picks, keeper surplus, counters regraded through the same pipeline, partner archetypes and tendencies, outcome tracking. Competitors (KTC, FantasyCalc, Dynasty Daddy, FantasyPros) mostly give crowd value totals. Engine v2 (#1571, open) adds expected lineup points, availability, waiver replacement, confidence and a lineup-aware counter search, which is the right foundation.

Ranked capabilities, with what exists and what is missing:

1. Deadline mode (new). A per-league countdown from `trade_window`; contender view ("buy": starters at your hole positions, price ceiling) vs rebuilder view ("sell": vets with value that decays, pick targets); push at T-7, T-2, T-1; extra free analyzer runs during deadline week; a "last call" summary of unfinished ideas. Effort M.
2. Accept probability (new, partly exists internally). `market_context.score` gates ideas by acceptance realism but is not shown. Surface a calibrated "likely to accept" label using partner needs, tendencies and past trades; calibrate against the outcomes table before showing a percentage. Effort M, depends on outcome volume, so start with 3 bands, not a number.
3. Partner finder improvements. Finder is Pro-only and idea-list based. Rank partners explicitly (needs, surplus, tendency, recent activity), show "why them" in one line, and make it the entry point from any player ("shop him"). Effort M.
4. Counter-offer generation (exists). Make it conversational: "they said no, what next?" generating a ladder of 3 counters, plus their-side view ("what would make them say yes"). Effort S-M after v2.
5. League-specific market (partial). Show what each manager recently paid for each position in this league (from `/history`, `team_trade_history`) and a league price index (is WR2 overpriced here). Effort M.
6. Trade history intelligence (partial). Whole-league trade desk with our grade on each completed trade, winners and losers, and "trades you missed". Existing outcome pipeline only covers the user's own shared trades. Effort M.
7. Sending the offer (missing). One tap to copy a ready-to-paste proposal and deep link to Sleeper; track it as the real "offer sent" event. Effort S.
8. Share and virality (partial). Attribution on QR, dynamic OG trade pages, a "verdict of the day" from the external feed, leaguemate invites that show the group's trades. Effort M.
9. Trust surface (missing). Every verdict says what it assumed (injury timing, waiver replacement, data date) in one line, with a "report a bad verdict" button feeding a review queue. This is cheap insurance for an ad campaign. Effort S.

Do not claim a win rate or accuracy for trades anywhere until outcomes have been measured; the value audit also found projections trail Sleeper.

## Ranked backlog: 15 best next moves

1. Merge and validate trade engine v2 (#1571): regression set of real-league screenshots, calibration script output reviewed, then ship. M. Gates every ad. (D, P)
2. Deadline mode v1: countdown card, `trade_deadline` push category (T-7/T-2/T-1), contender/rebuilder framing on Dashboard and Trade Hub, extra free analyzer runs in deadline week. M. (D, A)
3. Free-tier trade experience: replace the hard 3/week stop with a deadline-week allowance and show the best counter once for free; give Finder one free search. S-M. (D, P)
4. Public analyzer to account bridge: concrete "your roster" teaser after entry, dynamic OG image per shared link, UTM/ref on all share QR and links. M. (D, A)
5. Values freshness and trust: staleness banner and db-age alert, in-season production weight, injury severity discount, FantasyCalc suffix matching, cap teamless values. M. (D, P)
6. Accept-likelihood label (3 bands) on ideas and analyzer verdicts plus "why them" partner line. M. (D, P)
7. Send-the-offer handoff (copy proposal text, Sleeper deep link, "sent" event) and trade outcome follow-up tied to it. S. (D, A)
8. Verdict transparency line and "report a bad verdict" action on both platforms. S. (D)
9. Playoff odds "change from this trade" on analyzer plus a web Playoff Odds route (or an explicit parity exception). M. (D, A)
10. Premium conversion at the moment of value: contextual upsell on locked ideas/Finder with the specific blocked result, `checkout_completed` and paywall events. M. (P)
11. End-to-end referral verification (web and app), and prompt after a good trade result. S. (A)
12. Interactive sample league: run the real analyzer on the sample roster, usable before sign-up on web and app. M-L. (A, D)
13. Whole-league trade desk (completed trades with grades) and league price index. M. (A, D)
14. Roster-filtered News/Alerts with source and time and cross-outlet dedupe; article-driven push for starters only. M. (A)
15. Mobile analytics decision: either enable a minimal, consented funnel for iOS/Android or document the blind spot; add a server kill-switch for non-web platforms either way. S-M. (A, P)

## Cut / merge list (honest)

- Merge GM Plan "trade opportunities" and the Dashboard Trades block into one component fed by one engine call; they say the same thing in two places.
- Merge the three trade tabs into a single Trades entry with Analyzer as default and Finder/Ideas as modes (a `feat/consolidate-trades-tabs` branch exists); keep History and Community as secondary tabs.
- Hide Games (Guess the Player) and the Founder analytics and Design routes from the user app (staff flag). Keep Games only as an optional engagement module under More.
- Decide Community trades: fold into Trade Hub as "league feed" or hide until volume exists.
- Park College scouting, Live Draft and Draft Center in the nav until August (keep code).
- Rename or hide the GM orb on phone until it answers questions; today it is a menu with an assistant name.
- Remove or defer iOS Live Activities until Apple setup is done; do not mention in marketing.
- De-duplicate the rank strip and team-snapshot glossary notes on mobile (partly done in #1570).

## Risks and open questions

- Engine v2 changes verdicts; confidence cut points and shares are parameters, not validated numbers (per its own doc). Needs owner review of sample outputs before an ad push.
- Sleeper does not expose pending proposals publicly, so "import incoming offers" may be impossible; confirm before promising.
- Free-limit changes affect revenue; propose as an A/B or time-boxed deadline promotion.
- Mobile analytics policy (off) means iOS and Android conversion cannot be measured; decide knowingly.
- All grades are code-derived, not user-tested. A real-device pass at 390px (never done for Dashboard) should precede the campaign.
