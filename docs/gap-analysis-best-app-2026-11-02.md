# Gap analysis: "best fantasy football advice app" wishlist vs the code (2026-11-02)

Source: coridian_'s PDF "If I were building the best fantasy football advice app on the market" (13 sections plus the closing blueprint).
Method: every feature line in the PDF was checked against `origin/main` (read-only, by reading endpoints, modules and web/app components, not by file names).
Limits: code-derived only. No browser, device, prod query or logged-in session was used, so "BUILT" means the code path exists and is wired to a screen, not that it was click-tested or that the numbers are validated.
Supersedes the stale parts of `docs/FEATURE-AUDIT-2026-10-27.md` (deadline mode, verdict assumptions, report-a-bad-verdict, posture-aware verdicts and a web Games/season-sim page have all shipped since).
Status key: BUILT = works end to end on web and app (exceptions noted). PARTIAL = real piece exists, named part missing. MISSING = nothing user-facing.
Web = W, iOS/Android app = A.

## 1. Verdict

The app is already a roster-aware decision tool, not a calculator: the trade analyzer grades a deal against your lineup, your team posture, league scoring and the deadline, and Trade Hub, Trade Finder, GM Plan, the daily briefing, push alerts, league rankings, manager tendencies, weekly projections with weather, a season simulator and a live draft assistant all exist and are fed by one set of engines. The wishlist's central idea ("what is he worth to YOUR team and why") is mostly built for trades and lineups. The real gaps are the connective and accountability layers: championship/playoff odds are not wired into the Dashboard or into trade verdicts, waivers do not name the specific backup of an injured starter, there are no snap/target/route trend insights, no opponent position-by-position profile, no user-visible value history, no decision history or recommendation accountability, no post-draft grading/ADP/mock draft, no contract/future-roster projection, and no "ask the GM" (the backend has no LLM by design). The navigation is about 20 destinations, not six. Data-quality-before-AI (the PDF's own rule) matches what the team has been doing.

## 2. Status, section by section

### 1. Home dashboard

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Team health (roster strength, positional strengths/weaknesses) | BUILT | `GET /v1/leagues/{id}/dashboard` `team_snapshot` (power/franchise/starter/bench ranks, `health_flag`, injured starters); `GET .../my-team-needs` strengths, weaknesses, `biggest_need`, per-position groups. W `DashboardContent`, `MyTeamContent`; A `DashboardScreen`, `MyTeamScreen`. |
| Championship probability | PARTIAL | Real Monte Carlo with `title_probability` and `playoff_probability` (`modules/playoff_simulator.py`, `GET .../playoff-odds`, `.../games/season-sim`). Shown on Games (W `GamesContent`, A `GamesScreen`), GM Plan (W) and a playoff-odds strip on the app dashboard. Web Dashboard does not show it; title odds hidden when unavailable. |
| Power rankings | BUILT | `GET .../team-rankings` (`power_rank`, franchise, starter, bench, age, draft-capital ranks); W `LeagueRankingsContent`, A `TeamsScreen`; rank strip on Dashboard. |
| Team direction (contender/retool/rebuild) | BUILT | `modules/trade_posture.py` (declared Team Situation, else auto from roster + record + age + picks), `team_stance`, GM stance; `PostureChip`; feeds verdicts and ideas (#1597, #1599). |
| Weekly outlook (expected points, opponent projections, matchup difficulty) | PARTIAL | Matchup has projected totals, win probability, position edges (W `MatchupContent`, A `MatchupScreen`; `modules/matchup_win_probability.py`). On the Dashboard it is only a "Weekly Matchup" card under More on the app. "Difficulty" exists per waiver target (`opponent_defense_tier`), not as a weekly team rating. |
| Action items prioritized over stats | BUILT | `modules/this_week.py` "Now strip" (lineup, deadline, alerts, waivers), `daily_gm_briefing.py`, Dashboard order (`dashboardLayout.ts`, shared W/A). Docs: `docs/dashboard-reorg.md`. |

### 2. Trade Center

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| A. Player value | BUILT | Value engine + `trade_value_bands`; verdict `value_summary`, `value_delta`. |
| A. Team impact | BUILT | `modules/trade_lineup_model.py` / `trade_lineup_impact.py`: expected lineup points before/after over remaining weeks (league slots, byes, injuries, waiver replacement); `lineup_model.points`. |
| A. Positional need | BUILT | `roster_summary` plus fit engine `trade_analyzer_fit.py`, `roster_needs.py`; lineup warnings for holes. |
| A. Short-term vs long-term value | BUILT | `lineup_model.win_now_delta` / `future_delta`, posture window and direction terms (`trade_posture.py`). |
| A. Playoff impact (championship odds) | PARTIAL | Posture assessment carries `wins_delta`; verdict never states a playoff/title odds change. The simulator exists but is not called by the analyzer. |
| A. Risk assessment | PARTIAL | `risk_summary` text, confidence %, `verdict_assumptions.py` (what the verdict assumed), "Report a bad verdict" (`verdict_feedback.py`). No structured risk list (age cliff, injury history, workload). |
| A. Value is not universal (contender vs rebuilder) | BUILT | Posture-aware grading (#1597/#1599), valuation lens (Dynasty/Rebuild/Redraft). Ahead of PDF. |
| B. Trade Finder: teams with weak positions / excess depth / needing production | PARTIAL | Trade Hub ideas (`GET .../trade-hub`, `trade_hub_engine.py`, `trade_ideas.py`) are partner-aware with needs/surplus modeling and acceptance realism label (`market_realism_label`). Surplus-vs-need is internal to ideas, not a browsable league list. |
| B. Players whose value may be declining | PARTIAL | `sell_high` / `buy_low` impact tags on ideas; no scanner list. |
| B. Managers likely to sell | BUILT | `partner_trade_tendency` Buyer/Seller from real history (`team_trade_history.py`), `ManagerTendenciesCard`. |
| B. Realistic trades on actual rosters | BUILT | Trade Hub + Trade Finder (`GET .../trade-finder`, W `TradeFinderContent`, A `TradeFinderScreen`). Finder is Pro-only. |
| C. Trade Return Explorer ("what could I get for X / 2 mid WRs / a 1st", ranked by team improvement) | PARTIAL | Finder takes assets you shop (players and up to 4 picks) and returns partner packages (#1596). No "pick a return shape" builder; results ranked by idea priority, not by lineup-points gain. |
| D. Construct mutually beneficial trades | BUILT | Idea generator requires partner fit and acceptance plausibility. |
| D. Identify what another manager might want | PARTIAL | Partner need drives ideas; not shown as a "what they want" panel. |
| D. What the opponent will likely reject | PARTIAL | Realism meter on idea cards; not on manually built trades, and 3 bands, not a probability (correctly, until calibrated). |
| D. Counteroffers | BUILT | `build_counter_offer_packages` (regraded alternates, "Build the counter"), concrete counter or "No better package found" (#1582). |
| D. Know when you are overpaying | BUILT | Favorable / Fair / Slight Overpay / Major Overpay bands, lineup cost lines. |

### 3. Player Intelligence Center

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Current fantasy value, dynasty value | BUILT | Lens-based `value_score`, 0-99 overall rating, tiers. W `PlayerQuickView`, `PlayerProfileContent`; A `PlayerDetailScreen`. |
| Redraft value | BUILT | Lens "Non-Dynasty" (Redraft) in the evaluation lens control; league format auto-detects it. |
| Weekly projection | BUILT | `modules/player_projections.py` (`project_player_week`, point estimate plus low/high, confidence, weather). |
| Rest-of-season projection | PARTIAL | Lineup model estimates ROS points inside trades; no per-player ROS projection shown. |
| Career trajectory | BUILT | Career tab (`GET /v1/players/{id}/career`), awards, age/years in league. |
| Age and contract information | PARTIAL | Age and bio `contract_status` string in quick view. Real contract-year data (`modules/nflverse_contracts.py`) feeds only the external bot endpoint; no contract screen. |
| Snap %, target share, touch share, opportunity share | PARTIAL | Snap share and target share in quick view stats and percentile explorer (`percentile_explorer.py`), route participation when present; no opportunity/touch share tile. |
| Air yards, red-zone opportunities, routes run, YPRR | MISSING | Only college yards/route; no NFL air-yards, red-zone or routes-run pipeline. Needs a new data source. |
| Efficiency metrics | PARTIAL | Per-game and per-touch rate stats (`player_quick_view.py`), percentile explorer vs position. |
| Trends: last 4/8 weeks, season average, YoY | PARTIAL | Points-by-week chart with season selector (`PlayerTrendsPanel`), usage trend tile (up/down %, confidence; `_project_usage_trend`). No explicit L4/L8 rollups. |
| Fantasy production vs expected production | MISSING | No expected-fantasy-points model. |
| Intelligence: rising target share, snap growth, unsustainable QB, benefiting from injuries, rookie role expanding | PARTIAL | Usage-trend narration, model strengths/risks and `decision_fit_narrative`, opportunity labels (Handcuff, Backup With Upside). No cross-player "insight feed" and no injury-beneficiary detection. |

### 4. Waiver Wire Intelligence

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Best available, priority rankings | BUILT | `GET .../waivers`: players, `priority_adds` with confidence, stash/watchlist/FAAB shortlist (Pro). W `WaiversContent`, A `WaiversScreen`. |
| FAAB recommendations | BUILT | `modules/faab.py` bid guidance with low/high and data confidence; budget remaining; waiver mode (FAAB/rolling/reverse). |
| Roster-specific recommendations | BUILT | `needed_positions` from roster fit; priority adds ranked by need. |
| Injury replacement identification | PARTIAL | `injury_replacement_fit` flag plus note for adds at positions with injured starters. Does not say "X is injured, here is his direct backup". |
| Handcuff identification | PARTIAL | `Handcuff` / `Backup With Upside` opportunity labels (`rankings.py`); no explicit "handcuff for the RB on your roster" link. |
| Emerging players, snap-count trends | PARTIAL | Opportunity labels plus Sleeper global trending-add flag; no snap-count trend. |
| Ownership percentage changes | MISSING | Only Sleeper's global trending-add count; ESPN roster percentages (`public_roster_percentages.py`) feed public pages only. |
| Waiver Opportunity Scanner (injury -> backup -> workload -> availability -> value -> bid -> why) | PARTIAL | Pieces all exist separately (alerts action hint "possible priority add", injury fit, FAAB, availability from waivers); no single chained flow. Rental vs keeper distinction missing. |
| "Player you should drop" (closing example) | MISSING | No drop candidate recommendation. |

### 5. Start/Sit Intelligence

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Weekly projections, injury status, bye/ruled out | BUILT | Matchup suggested moves (`MatchupSuggestedMove`: gain, bye_week, ruled_out, locked) from `matchup_what_if.py`. W `MatchupContent`/`MatchupPlanner`, A `MatchupScreen`/`MatchupPlanner`. |
| Defensive matchup | BUILT | Points-allowed-by-position in `player_projections.py`. |
| Weather | BUILT | `modules/game_weather.py` measured, capped effects (`docs/weather-effects.md`), `WeatherReasonChip`. Ahead of PDF. |
| Floor and ceiling | PARTIAL | Projection carries low/high (68% interval); not shown side by side in Matchup moves. |
| Expected workload, recent usage | PARTIAL | Usage-weighted projections; not displayed as workload. |
| Game script projections, historical matchup | MISSING | No game-script or per-opponent history. |
| Boom/bust probability | MISSING | |
| Explain the recommendation | BUILT | Each move carries gain and reason chips. |
| "Play for the ceiling when projected to lose" | MISSING | Win probability and low/high both exist; nothing combines them. |

### 6. League Intelligence

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| League-wide analysis per team: roster strength, starting lineup, bench, draft capital, direction | BUILT | `TeamRanking` fields (power, starter, bench, draft capital, strategy label, archetype with strengths/risks/recommendations, injuries). W `LeagueRankingsContent`, A `TeamsScreen`. |
| Positional rankings per team | PARTIAL | Only the user's own rooms (`my-team-needs`). Opponents only get position needs inside trade ideas. |
| Biggest weaknesses, potential trade partners | PARTIAL | Archetype risks and partner discovery in Draft Center; no "who fits me" board. |
| Opponent profile (strongest/weakest position, depth, picks, suggested offer) | PARTIAL | `ManagerProfileSheet` (W) / manager tendencies (`manager_tendencies.py`: trade, waiver and add behavior with minimum sample sizes), recent trades with grades, pick flow (`pick_flow.py`). No per-position strength/weakness or "offer this" line. |
| League trends: players acquired/dropped, teams accumulating picks, pursuing championship, likely sellers | PARTIAL | League Pulse, storylines (`league_storylines.py`), recaps, all-trades, team badges (Pick Hoarder/Seller, Hot Streak), buyer/seller tendency. No "most added/dropped players in my league" board. |
| Commissioner integrity (not in PDF) | BUILT | `commissioner/integrity`, W/A Commissioner. Ahead of PDF. |

### 7. Draft Center

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Custom rankings | MISSING | Lens-based rankings only; no user-edited board. |
| Mock drafts | MISSING | |
| ADP comparisons, value vs ADP | MISSING | No ADP source anywhere in code. |
| Positional tiers | PARTIAL | Player tiers exist (`player_tiers.py`) and show in rankings; no draft-board tier cliffs. |
| Rookie rankings | PARTIAL | College Scouting (crowd grades, round projections, `college_scouting.py`) plus rookies in rankings; no dedicated rookie board. |
| Draft strategy recommendations, draft capital analysis | BUILT | `GET .../draft-center` (posture, decision cards, partner cards), `draft-picks` with pick range projection and class strength. A `DraftCenterScreen`/`PickDetailScreen`, W `DraftCenterContent`. Web has no pick-detail page. |
| Live assistant, best available, team needs, positional scarcity | BUILT | `GET .../live-draft/{draft_id}` with Best Overall/Value/Fit/Safe/Upside/Avoid buckets, positional run, live team board (`draft_assistant.py`). Pro. W `LiveDraftContent`, A `LiveDraftScreen`. Not click-tested on a real draft (`docs/roadmap.md`). |
| Opponent tendencies in the room | MISSING | Manager tendencies are not used in the draft room. |
| Trade up/down recommendations | PARTIAL | Hypothetical mid-draft trade evaluator (`live_draft_trade_evaluator.py`), no proactive suggestion. |
| After draft: pick grades, round analysis, best value, biggest reaches, team projection, league comparison | MISSING (helpers unused) | `draft_assistant.grade_completed_draft_pick` / `completed_pick_review_rows` exist but are not called by any endpoint. League Recaps grade transactions, not draft picks. |
| Draft becomes permanent history | MISSING | |

### 8. News and Injury Intelligence

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Personalized, roster-impact prioritization (high/medium/low) | BUILT | `news_intelligence.py` severity (critical/high/...), roster relationship (mine/opponent/free agent), `GET .../alerts`; W `AlertsContent`, A `AlertsScreen`. |
| What happened / what to do | BUILT | Alert copy and `action_hint` (e.g. "Open Waivers: possible priority add"). |
| How it affects fantasy value | PARTIAL | Value adjustment from news is behind a flag (`DYNASTYGM_NEWS_VALUE_EVENTS`, default off; `docs/news-value-events-2026-10.md`); alerts say `valuation_impact: none_from_article`. |
| "Backup snap share +15%" style items | MISSING | Alerts come from news and Sleeper injury status, not usage changes. |
| Intelligent, not constant notifications | BUILT | Push caps (4/week), quiet hours, per-category toggles, reserved slots for injury/lineup lock/deadline (`push_triggers.py`). |

### 9. Dynasty-specific

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Dynasty rankings, long-term values | BUILT | Rankings, public SEO pages (`/dynasty-rankings`, `/dynasty-trade-value-chart`). |
| Rookie rankings, prospect evaluation | PARTIAL | College Scouting (see 7). |
| Draft capital, future pick valuation | BUILT | `trade_ideas.list_draft_pick_assets`: round, expected early/mid/late range from original team, class strength, years-out discount (`future_discount`). Pick Detail on app only. |
| Pick intel: opportunity cost, historical hit rates | MISSING | Not modeled. |
| Future draft capital visualization (yours vs everyone) | PARTIAL | Draft-capital rank and first-rounder counts per team; no chart. |
| Age curves, career trajectory | BUILT | Age curve inside valuation (`docs/valuation-quality-age-production.md`), career tab. |
| Contract tracker | MISSING (data exists) | `nflverse_contracts.py` (years, signed, active; deliberately no dollars) used only by the external bot. |
| Rebuild analyzer / Contender analyzer | PARTIAL | Posture classification, archetypes with strengths/risks, GM Plan phase roadmap, deadline mode ("buy a starter" / "sell aging depth"). No dedicated "championship readiness / rebuild timeline" score. |
| Future roster projection | MISSING | No multi-season projected roster strength. |
| Pick value calculator | BUILT | Picks in Trade Analyzer, public analyzer, trade value chart. |
| Trade calculator | BUILT | Trade Analyzer (W, A), public `/trade-analyzer`. |

### 10. AI General Manager

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Ask-anything GM (contender? weakness? rebuild? who to target? deadline plan? buy low? 3-week plan? trade my 1st?) | MISSING | GM orb is navigation plus player search only (`GmOrb.tsx`). `DEPENDENCIES.md`: no AI API anywhere in the backend. Several of the example questions are answerable today by the separate engines (posture, `biggest_need`, deadline card, GM Plan, Trade Hub); none is routed from a question. |
| Reasoning across roster, settings, opponents, projections, history, trade history, waivers, picks, news, injuries | PARTIAL | The engines have all these inputs; GM Plan and the Dashboard compose them. No single cross-engine reasoner. |
| Proactive GM recommendations | BUILT | Daily briefing, Next Moves, Top Trade Opportunity, GM Plan items, `top_priority`/`watch` pushes, deadline pushes. The PDF's exact example (RB-rich opponent, offer for their WR2) is the Trade Hub idea shape. |
| "What happens if I trade my 1st" | PARTIAL | Analyzer with a pick; no framing as a what-if on the season outlook. |

### 11. Overlooked features

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Decision history | PARTIAL | Server `modules/decision_memory.py` + `decision_change_history.py` (tables exist; module docs say default ON), app "since your last check-in" diff (device-local), Trade History for shared trades. No decision-history page on either platform. |
| Recommendation accuracy / accountability | PARTIAL | Trades the user confirmed are graded later (`trade_outcome_results.py`, W/A Trade History, push follow-up). Waiver and start/sit recs are not recorded or scored. Internal weekly projection backtest (`docs/projection-scoreboard.md`: our model beats season-average, trails Sleeper) is not user-facing. |
| What-if simulator | PARTIAL | Season Simulator add/drop what-if (Pro, W+A Games), matchup lineup planner (W+A). No trade what-if on odds. |
| Player value history | PARTIAL | Daily 0-99 rating snapshots (`player_rating_history.py`) and value-change diffs (`player_value_history.py`) feed the external bot only; no chart in the app. |
| Opponent tendencies | BUILT | `manager_tendencies.py`, `GET .../managers/{roster_id}/tendencies`, W profile sheet, trade-idea tendency chips. Evidence-backed with minimum samples. Ahead of PDF on honesty. |
| Trade deadline strategy | BUILT | `league_calendar.trade_window`, deadline card, buy/sell framing, `trade_deadline` push at 2 wks / 1 wk / deadline week (`docs/dashboard-reorg.md`). |
| Playoff path analyzer (potential playoff opponents) | MISSING | Simulator gives odds, not bracket or likely-opponent paths. |
| Roster risk assessment (injury, age, workload) | PARTIAL | Injury health flag, injured starters, archetype risks, average age. No combined risk score. |
| Market inefficiency scanner | PARTIAL | Buy-low/sell-high tags on ideas; external "interesting trades" feed computes market gaps. No user-facing scanner. |
| Automated weekly report | PARTIAL | League Recaps (league-wide weekly stories), daily briefing; the old team Weekly GM Report was Streamlit-only and is gone. No per-team weekly report. |

### 12. Navigation and structure

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Six destinations | PARTIAL | `navDestinations.ts`: 7 core league pages, Trade Hub, GM Plan, Draft Center, Live Draft, Recaps, Games, Commissioner, plus Portfolio, News, Trade History, College Scouting, Community. Trade Finder/Analyzer already merged under Trade Hub tabs. No Research hub; League and Draft are spread over several entries. |
| AI GM accessible everywhere | PARTIAL | GM orb is on every screen but is navigation, not an assistant. |
| Mobile-first, expandable cards, detail on demand | BUILT | Shared module system, quick view sheets, Read-more collapse, density toggle. |

### 13. Priorities and data quality

| PDF line | Status | Evidence / what is missing |
|---|---|---|
| Phase 1: accurate data, league sync, dashboard, roster analysis, player intelligence | BUILT (player intel PARTIAL) | Sleeper sync; ESPN/Fleaflicker/MFL imports with fewer pages (`docs/platform-import-status.md`); refresh and sync workflows. |
| Phase 2: trade intelligence, waivers, start/sit, league analysis | Mostly BUILT | See above. |
| Phase 3: AI GM, proactive recs, what-if, dynasty analytics | PARTIAL | Proactive recs built; AI GM and trade what-if missing. |
| Phase 4: draft ecosystem, recommendation tracking, advanced predictive analytics | PARTIAL | Live draft built; post-draft, ADP, mock, tracking missing. |
| "Data quality over AI sophistication" | Aligned | Honest-uncertainty rules throughout (no label below minimum sample, unavailable states instead of guesses), valuation audits, projection backtest published weekly. |

### Memory-level priorities (roadmap gaps from 2026-09-17)

| Item | Status |
|---|---|
| Premium lifecycle audit, mobile QA, cross-platform persistence (P0) | Done in Sept (PRs #541, #548, #539). Not a PDF gap. |
| Trade Outcomes (P1) | Built (table, prompt, sweep, history page, grading). The PDF's "accountability" asks for the same loop on waivers and start/sit. |
| Decision Memory (P1) | Two different things: the change-history log is built (backend), the "GM intent memory" concept was marked needing a product conversation. Neither has a user-facing history page. |
| GM Plan (P1) | Built (phase-aware, merged with GM Targets and Team Situation). |
| PQV depth (P1) | Decision-fit narrative, availability block, usage trend, full profile page all shipped. Advanced stats are the remaining depth gap. |

## 3. Already ahead of the PDF

- Posture-aware trade verdicts that know contender vs rebuild window and direction (#1597, #1599), plus a one-line statement of what each verdict assumed and a "Report a bad verdict" action.
- Trade outcomes: confirm "did it happen", later graded by real production and value trend; anonymized Community trade feed with reactions.
- Manager tendencies computed only from real transactions with minimum samples ("not enough data" instead of a guess).
- Weather-adjusted projections using measured, capped effects; published weekly projection scoreboard against Sleeper and season average.
- Deadline mode (card, buy/sell framing, three push tiers), commissioner integrity tools, guillotine and keeper/IDP support, multi-league Portfolio with exposure, referral program, share cards with QR, mini-games and pick'em, college scouting with crowd grades.
- Uncertainty is shown honestly: unavailable states, low/high ranges, confidence labels, 3-band acceptance realism rather than a made-up percentage.

## 4. Top 10 missing or partial items, ranked by user value vs effort

Effort: S under 2 days, M up to about a week, L multi-week. Includes web and app (parity rule) unless noted.

| # | Item | Why it ranks here | Effort |
|---|---|---|---|
| 1 | Championship/playoff odds in the decision loop: show on web Dashboard, add "odds change" to trade verdicts and Trade Hub ideas by calling the existing simulator with the post-trade roster | Closes the PDF's biggest connective gap ("how adding him changes your playoff probability"). Simulator, what-if endpoint and Roster Power recompute already exist; Dashboard wiring is small, trade impact is the bulk. Must stay honest about simulator limits. | S (Dashboard) + M (trade impact) |
| 2 | Waiver Opportunity Scanner: when a starter is hurt, name the direct backup, show projected role, availability in this league, FAAB bid, "rental vs keep" | All pieces exist unchained (alerts hint, injury fit, FAAB, handcuff labels). High weekly use. | M |
| 3 | Start/Sit depth: show floor/ceiling side by side, and "you are a heavy underdog, ceiling matters" using win probability + low/high | Replicates the PDF's own example; both inputs exist. No new data. | M |
| 4 | Opponent profile cards: strongest/weakest position, depth, surplus, picks, "offer this" CTA that opens the analyzer prefilled | Makes every trade idea explainable; needs per-roster rooms for non-user teams (reuse `roster_needs`). | S-M |
| 5 | Usage-trend intelligence: L4/L8 snap/target/touch rollups, "role expanding" flags in player profile, waivers and alerts | Highest-value player-intel gap and feeds #2 and news. Data (weekly rows with snap share, targets) is already retained; advanced stats (air yards, routes, red zone) need a new source and are a later step. | M (rollups) / L (advanced stats) |
| 6 | Player value history chart + market-inefficiency list ("buy low / sell high now") | Data already stored daily (rating snapshots) but not shown to users. Cheap trust and engagement win. | S-M |
| 7 | Decision History page (web+app): recommendations seen, trades shared/confirmed/graded, lineup changes | Server log and outcomes exist; needs a unified timeline, account required. Foundation for #8. | M |
| 8 | Recommendation accountability: record trade ideas, waiver adds and start/sit calls shown, score against real outcomes, show a "how my GM is doing" summary | The PDF's most important "trust" feature. Needs server-side logging (not analytics) and enough volume; do not publish accuracy claims until measured. | L |
| 9 | Draft after-action: pick grades, reaches/best values, round analysis, permanent draft history (helpers exist, unwired); ADP/mock later | Offseason value; low effort for the review half, ADP/mock needs a data-source decision. | M (review) / L (mock + ADP) |
| 10 | "Ask the GM": deterministic intent router that answers the PDF's example questions from existing engines (posture, biggest need, deadline plan, targets), LLM optional later | The PDF's top differentiator, but conflicts with the no-AI-API stance until decided; a deterministic version delivers most of it without new data or vendors. | L |

Also worth queuing (not top 10): future roster projection and contract tracker (M-L, nflverse contract data exists), six-destination navigation consolidation (M, product call), per-team weekly report (M, compose from briefing + matchup + recap), web Pick Detail page (S).

## 5. Suggested three-phase order

Phase 1, in-season decision loop (next 2-4 weeks, deadline season): #1 odds in Dashboard and trade verdicts, #4 opponent profile, #3 start/sit floor/ceiling, #6 value history. All reuse existing engines and need no new data source.

Phase 2, depth and memory (about 1-2 months): #2 waiver scanner, #5 usage-trend rollups, #7 decision history, per-team weekly report, web Pick Detail. Start server-side logging for #8 here so volume accumulates.

Phase 3, offseason (before spring rookie drafts): #9 draft review, ADP/mock (after a data-source decision), future roster projection and contract tracker, #8 accountability summary once volume exists, #10 Ask the GM, navigation consolidation, advanced stats pipeline if a source is approved.

## 6. Conflicts with held decisions (read before scoping)

- Analytics stays OFF on mobile (and server write default is off): recommendation accountability and decision history must be built on server-side tables (like `trade_outcomes`), never on client analytics events. Do not read anything from `analytics_events` to compute accuracy.
- Guests cannot buy: new Pro-gated features (scanner, odds-impact, accountability) need a signed-in path to the paywall; decision history and accountability need an account (guests have no persistence), so guests should see a "save your front office" prompt, not a broken page.
- Legal items held: hosted leagues/college and anything contest-like are held (`docs/plan-hosted-leagues-and-college.md`, `docs/engagement-brainstorm-2026-10.md`). Game-script and Vegas-line inputs for start/sit touch sportsbook-adjacent data and the same brainstorm flags betting comparisons as a risk: either skip them or get a decision first. ADP and licensed rankings data need a license check before use. Contract dollars were deliberately excluded from `nflverse_contracts.py`; keep it that way unless approved.
- AI GM vs "no AI API": `DEPENDENCIES.md` records that no LLM vendor is used. An LLM-backed GM would change the privacy policy, App Store data disclosure and subprocessor list. The deterministic router in #10 avoids this; an LLM needs an explicit owner decision.
- No fabricated data: do not ship a championship-odds change, boom/bust probability, accept probability, "expected production" or accuracy percentage that is not computed from real inputs and calibrated. Keep the existing pattern (unavailable state, ranges, 3-band labels). The projection scoreboard shows our model trails Sleeper's, so never market projection accuracy as better than measured.
- Parity rule: every item above ships on web and iOS/Android together, or notes an exception (Pick Detail, Teams/Roster are app-only today).
- Mobile-only ads/analytics code is stubbed or off; do not rely on them for any item here.
