# Missing user journeys: what a dynasty manager expects to DO (2026-11-03)

Trigger (Zach/turbo, from the owner): there was no way to start a trade by picking a player on another team ("get this player", engine builds the package). Find the other obvious things like that, without making the app convoluted or hiding things.
Method: ~44 verbs from the user's side, each traced in `web-next/src`, `mobile/src`, `services/mobile_api_service.py` and `modules/`. Greps were run before anything is marked MISSING. Code-derived only: nothing was click-tested, no device or logged-in session.
Skipped on purpose: Ask the GM chat (owner said no), rookie draft pick data (decided to skip), anything legal or billing-held.
Builds on `gap-analysis-best-app-2026-11-02.md` (feature coverage) and `ux-utilization-audit-2026-11-03.md` (tap depth). This doc is about verbs, not screens. Some items there are now stale, noted below.

Status key: EASY = exists, one tap from where the user is. HIDDEN = exists but deep, one entry point, or differs web vs app. PARTIAL = a real piece exists, the verb is not finished. MISSING = grep found nothing user-facing.
W = web, A = iOS/Android app.

## 1. Table

### Trades

| # | Verb | Status | Evidence |
|---|---|---|---|
| 1 | "Get that guy" (pick a player on another team, engine builds the offer) | **MISSING** | Quick View shows "Add to Trade" for any rostered player (`PlayerLeagueActions.tsx`, `lib/tradeShortcuts.ts`, A twin `mobile/src/lib/tradeShortcuts.ts`). That only pre-fills the Analyzer's receive side; the user must build the give side by hand. The engine already has this: `build_player_trade_hub_ideas(mode="target_player")` in `modules/trade_ideas.py` (~L7614, `explicit_acquisition_target=True`). Grep: no endpoint in `mobile_api_service.py`, and no web or app code calls it. Trade Finder only starts from players you OWN (`trade_block_player_ids`, `TradeFinderContent.tsx`). |
| 2 | Check a trade is fair before sending | EASY | Trade Analyzer (`/trade-analyzer/[leagueId]`, A `TradeAnalyzerScreen`). Value balance, lineup model, posture, risk text, report-a-bad-verdict. Public version at `/trade-analyzer`. |
| 3 | "That's not good enough, fix it" (counter) | EASY | Verdict has `counter_guidance` + "Build the counter" and "Try this instead" `alternate_packages` (`TradeAnalyzerContent.tsx` ~L483-540; `mobile_api_service.py` ~L6067 `counter_search`). Only appears after you built a first offer. |
| 4 | Sell a player at his peak | PARTIAL | "Find trades" on your own player in Quick View (W+A) runs Trade Finder (Premium). `sell_high` tags on Trade Hub ideas. `ValueSignalsCard` (Buy low / Sell high) lives only on Trade Hub (W `TradeHubContent`, A `TradeHubScreen`) and is league-wide, not filtered to your roster: `GET /v1/players/value-signals` takes no league id. |
| 5 | See which of MY players are dropping in value | PARTIAL | Per-player rating history chart in Quick View / profile (`PlayerValueHistory.tsx`). A value-trend tile exists in Game Plan (see `HighlightTarget` comment in `MyTeamContent.tsx`). No "my roster, biggest value movers" list on My Team. |
| 6 | What should I offer for a pick / what is my pick worth | PARTIAL | Picks are assets in Analyzer and Finder (up to 4 picks, `TradeFinderContent.tsx`), `GET .../draft-picks`. A has Pick Detail (`PickDetailScreen`); W has no equivalent (audit: "None"). No "what would a team pay for this pick" start point. |
| 7 | Find a trade partner for MY player Z | EASY (own players) | Quick View "Find trades" -> Trade Finder pre-run (`gamePlanTileHref("trade-finder", ...)`). Premium. |
| 8 | Trade my surplus at X for need at Y | PARTIAL | My Team shows needs and surplus (`MyTeamSections.tsx`, `GET .../my-team-needs`) with no outbound links (audit 3.1). Trade Hub ideas are built on surplus/need fit (`trade_ideas.py`). The user cannot say "I want a WR, I will pay with my RB surplus". |
| 9 | See what a team needs so I can pitch them | HIDDEN | Manager profile sheet: strongest/weakest room, surplus, needs, picks, trade angle, "Offer this" (`OpponentProfileCard.tsx`, `GET .../teams/{roster_id}/profile`). Only opened from a team row in League Rankings (W) / Teams (A). Trade idea cards and the Analyzer partner row show tendency chips but do not link to it. |
| 10 | Offer a team what they need, one tap | PARTIAL | "Offer this" in the opponent card opens the Analyzer with ONE player pre-filled (`offerCaption`). It does not build the rest of the package. Same shape as row 1. |
| 11 | Who is a buyer / seller in my league | EASY | `partner_trade_tendency`, `ManagerTendenciesCard`, team badges, League Pulse. |
| 12 | Send the offer | PARTIAL | Share image/text and Community post exist. No "open Sleeper to propose" link from a verdict (Waivers and Matchup have one; grep of Analyzer and `TradeIdeaCard` found no Sleeper link). Sleeper has no write API for trades, so a link plus copy-text is the realistic answer. |
| 13 | Did my trade work out (accountability) | EASY on W, HIDDEN on A | Trade History/outcomes, "did it happen?" prompt (global). A: More only (audit 2.1). |
| 14 | Compare two players | EASY | Quick View "Compare this player" (W+A), `/player-compare/[leagueId]`. No entry from the Analyzer verdict or Waivers (audit 3). |
| 15 | Deadline plan | EASY | `DeadlineCard`, deadline push, Trade Hub deadline mode. |
| 16 | Mark a player untouchable / shop-only | HIDDEN | GM Targets untouchable flag feeds `trade_hub_engine` (`untouchable_player_ids`). Managed inside GM Plan; no toggle on Quick View for players you own. |
| 17 | Set a price/value alert ("tell me when X drops") | **MISSING** | Grep `price_alert / value_alert`: nothing. Alerts are news and injury only (`news_intelligence.py`, `AlertsContent`). GM Targets (watch list) has no change notification found in `modules/alert*.py`. |
| 18 | See who owns a player I just saw | PARTIAL | Add to Trade selects the owning team after the click. Quick View itself does not name the owner (audit 3.1: "manager who owns him" open). |

### Lineup, waivers, roster

| # | Verb | Status | Evidence |
|---|---|---|---|
| 19 | Who should I start | EASY / HIDDEN | Matchup suggested moves, `RangeCompare`, Lineup Planner (`MatchupPlanner.tsx`, `startSitRange.ts`). The planner swap sheet is behind "Edit lineup" (one entry point, audit 3). |
| 20 | Best waiver add for my need | EASY | `WaiversContent.tsx` priority adds, stash, FAAB, position snapshot. Full board Premium. |
| 21 | Who do I drop for him | EASY | `SuggestedDrop.tsx` in Waivers (W+A) and Analyzer roster overflow. The audit's "drop = data gap" is stale. |
| 22 | Add a free agent from a player card | PARTIAL | A Quick View has "View on Waivers" only if he is on the waiver list (`PlayerQuickViewSheet.tsx` ~L117-180). W Quick View has Add to GM Targets for non-owned players, no waiver link. Neither has "Open in Sleeper to add". |
| 23 | Injury news -> what do I do | EASY | Alerts with `action_hint`, cross-link rows (shipped 11-03), Now strip. |
| 24 | Keeper decisions | EASY | `GET .../keepers`, round-penalty control in My Team (W `MyTeamContent`, A `MyTeamScreen`). Keeper leagues only. |
| 25 | Watch a player I might want | EASY | Add to GM Targets in Quick View (non-owned players), A header star. |
| 26 | My roster by age/position/health | EASY | My Team, roster tabs, `team_snapshot`. |

### League, draft, long term

| # | Verb | Status | Evidence |
|---|---|---|---|
| 27 | How good is every team / power rankings | EASY | League Rankings (W), Teams (A). |
| 28 | My playoff / title odds, what-if | EASY (A) / HIDDEN (W) | A nav row; W only via League Rankings button, Games, Dashboard strip. Naming mismatch "Games" vs "Playoff Odds" (audit 5). |
| 29 | Weekly matchup preview | EASY | Matchup (W+A). |
| 30 | What happened in my league | EASY | Recaps, storylines, all-trades, League Pulse. Dead-end screens (no onward link). |
| 31 | Rookie draft prep | PARTIAL | Draft Center (picks, posture, partner cards), College Scouting (Pro, A hidden until opt-in), Live Draft assistant. No mock draft, ADP or custom board (gap analysis section 7). Pick data intentionally skipped. |
| 32 | Live draft help | EASY | Live Draft (best available, positional run, trade evaluator). |
| 33 | Look up any player (value, stats, news) | EASY | Header search + Players list + Quick View from 13 surfaces. |
| 34 | Value chart / "what is a 1st worth" | EASY (public) | `/dynasty-trade-value-chart` public page; picks inside Analyzer. In-app link not verified. |
| 35 | All my leagues at once | EASY | Portfolio (Premium wall for 1 league), `GET /v1/portfolio/exposure`. |
| 36 | Contract / years left | MISSING (data exists) | `nflverse_contracts.py` feeds only the external bot (gap analysis section 9). |
| 37 | Future roster / multi-year projection | MISSING | Gap analysis section 9. |
| 38 | Get pinged without opening the app | EASY (A), MISSING (W) | `push_triggers.py`, 9 categories. W has no push or email, yet Account lists push toggles (audit 2.4). |
| 39 | Import non-Sleeper leagues | EASY | ESPN import (`EspnImportForm`). Other hosts not traced. |
| 40 | Export / delete my data | EASY | `GET /v1/me/export`, Account delete. |
| 41 | Understand why a number is what it is | EASY | "How We Evaluate", `BeginnerHelp`, `verdict_assumptions`, factors on value signals. |
| 42 | Share a take (player, compare, trade) | EASY (W trade/idea/player; A also compare, portfolio, recap) | Audit 2.3. W lacks compare/portfolio/recap share. |
| 43 | Switch leagues fast | EASY | League switcher in header. |
| 44 | "What should I do today" | EASY | Dashboard Now strip, Today, Game Plan (free: 4 moves). |

## 2. Ranked gaps (top 10)

Ranking = how often the verb comes up for a dynasty manager x how badly the app fails now x how little new code it needs. Effort: S = days, M = about a week, L = multi-week.

1. **"Get this player" (target-player trade search).** Entry point: a primary button "Get him" on Quick View / player profile for any player you do not own, next to Add to Trade. It runs the existing target-player engine and shows 3 to 5 offers built from your roster, each with "Open in Analyzer". Reuse: `build_player_trade_hub_ideas(mode="target_player")`, Trust enforcement, the Trade Finder idea card and result list, `PlayerLeagueActions`. Needs one new endpoint (for example `GET .../trade-finder?target=<player_id>` or a sibling route) plus the result list. Effort **M**. Parity: build both at once; `tradeShortcuts` already has a W/A twin pair, add a `canGetPlayer` rule to both. Gate it like Finder (Premium, with the button visible to free users); keep Add to Trade free.
2. **Make both "Offer this" paths call #1.** Entry: the opponent card's "Offer this" asks for that player and the engine builds the give side; the Analyzer shows "Build me the offer" when it opens with only a receive side. Reuse: #1 plus the existing `offerCaption` target. Effort **S** once #1 exists. Parity: `OpponentProfileCard` (W) and `ManagerProfileModal` (A) share the pattern.
3. **Link idea cards and the Analyzer partner row to the manager profile.** Entry: tap the partner name or tendency chip. Reuse: `ManagerProfileSheet` / `ManagerProfileModal`, which already take a roster id but only open from League Rankings/Teams. Effort **S**. Parity: both platforms.
4. **My Team "value movers".** Entry: a small strip on My Team listing your players with the biggest rating change, each with Find trades (falling) or Hold (rising). Reuse: `rating_change` from `GET /v1/players/value-signals` / `player_rating_history.py` filtered to the roster, and the `ValueSignalsCard` row. Also show the existing Buy low / Sell high card (today only on Trade Hub) filtered to my roster. Effort **S/M**. Parity: A has `ValueSignalsCard` too; do both.
5. **Needs/surplus -> trade (My Team).** Entry: on each need or surplus row, a button "Find a trade for this" (need: Trade Hub ideas filtered to that position; surplus: Find trades with those players preselected). Reuse: `my-team-needs`, `tradeHubFilters.ts`, Finder preselect via `?playerId=`. Effort **S/M**. Parity: both My Team screens, same payload.
6. **Value alerts on watched players.** Entry: when you add to GM Targets (or star a player you own), one line "Alert me on big value moves", on by default. Reuse: GM Targets list, rating snapshots, existing push categories and the Alerts feed; no new settings screen. Effort **M**. Parity: push is A only; W gets the Alerts feed and bell. Needs a decision on Premium gating.
7. **Open in Sleeper from a verdict and from a free agent's Quick View.** Entry: "Propose in Sleeper" under the verdict (copies the offer text first), "Add in Sleeper" on a free agent. Reuse: the Sleeper link already shipped on Waivers and Matchup, `tradeCopy.ts` share text. Effort **S**. Parity: both.
8. **Pick-first start point.** Entry: on a pick row (Draft Center, Analyzer pick picker, A Pick Detail) a button "What could I get for this pick?" that opens Finder with that pick preselected (Finder already accepts up to 4 picks). Effort **S** for the button, **M** to add a W Pick Detail. Parity gap: Pick Detail is A only.
9. **Owner and need-fit line on Quick View.** Entry: one line under the name, "Owned by Team X (they need RB)" for rostered players, "Free agent" otherwise; tapping opens the manager profile. Reuse: `rosters` + `team-profiles`, and `PlayerLeagueActions` already loads rosters. Effort **S**. Parity: both Quick Views.
10. **Lineup Planner without "Edit lineup", and Compare from Analyzer/Waivers.** Entry: a swap icon on each weak starter row in Matchup suggested moves; a "Compare" chip on a waiver card and on each side of the Analyzer. Reuse: `MatchupPlanner`, `/player-compare`. Effort **S**. Parity: both.

Worth a line but not top 10: contract years (data exists in `nflverse_contracts.py`, one row on Quick View, **S**); web push or email (Account promises push that W cannot deliver, **L**); untouchable toggle on Quick View for owned players (**S**).

## 3. Web vs app parity gaps found

- Pick Detail: A only (no W route).
- Playoff Odds: A has its own nav row; W has none (button in League Rankings, Games, Dashboard strip).
- Trade History / Community / College Scouting / Guess leaderboard: W nav; A buried in More or a feed inside Trade History.
- Share: A shares compare, portfolio, recap; W does not.
- "What changed since last check-in" and push: A only.
- Quick View "View on Waivers": A only (W shows GM Targets instead).
- Everything else in the table is wired on both.

## 4. Avoid-convolution rules

- **Put the button where the thought happens.** The verb goes on the player, team row or pick the user is already looking at (Quick View, manager sheet, My Team row). Not a new nav item, tab or page.
- **One primary action row, no second one.** New actions share the existing Quick View action row and keep a fixed order: Add to Trade, Get him, Watch. Do not add a competing primary button.
- **Reuse engines and result lists.** New journeys call trade_grade, opponent_profile, roster_value_model, trade_hub_engine or the Finder result cards. No parallel "mini finder" with its own look or wording.
- **Show, do not hide.** Free users see the button with a one-line limit (the Trade Hub "showing 2 of N" pattern), not a missing button. Never show a button on a guess: the existing ownership rule (`tradeShortcutsFor`) stays.
- **Ship web and app together, same words.** Same label, placement and gate on both. Anything that cannot match (push, Pick Detail) is written down as an explicit exception in the PR.
