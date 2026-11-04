# Commissioner tools: League integrity

Request (coridian_): "a commissioner section where you can see if teams are
purposefully tanking and stuff". Engine: `modules/league_integrity.py` (pure,
testable). Data gathering and cache: `modules/league_integrity_data.py`.
Endpoints: `GET /v1/leagues/{id}/commissioner/integrity?draft_order=unknown|record|lottery`. Web:
`/commissioner/[leagueId]`. App: `Commissioner` screen. Shared presentation:
`lib/commissionerIntegrity.ts` (SHARED block byte-identical on web and app,
checked by a mobile test).

## Who sees it

Owner decision (coridian_): the section is Pro-only and does NOT depend on
being the league's commissioner. Any Pro user can open it for any Sleeper
league they can access (same league-access and `_is_pro_caller` gating as
Playoff Odds; trialing counts as Pro; Free gets the upsell and no data).
There is no commissioner detection (re-confirmed 2026-11-03: it stays open to any Pro user who can access the league; copy and code comments no longer say "for the commissioner"). It is framed honestly as a league-integrity
view over public Sleeper data: signals to check, not accusations. ESPN/MFL and
other imported leagues are not supported (`unsupported_platform`). Endpoint:
`GET /v1/leagues/{id}/commissioner/integrity`. Nav entry "Commissioner" sits
under GM Tools on web (sidebar, GM Orb) and the app (GM Orb).

## What it reads

Only public Sleeper data plus the shared valued players frame (read-only):
each completed week's matchup (`starters`, `players`, `players_points`),
rosters, users, season transactions, and the nfl schedule (bye weeks). It
never calls `rankings.load_players`.

Weeks evaluated: completed regular-season weeks only (before the current
Sleeper week, before `playoff_week_start`). Playoff and consolation/toilet-bowl
weeks are excluded, so those formats never count. Best-ball leagues are
skipped (`best_ball`).

## Signals

Per team, per week:

1. Lineup efficiency (context only). Actual starter points vs the best legal
   lineup from the roster that week (hindsight). Everyone has a gap, so this
   is shown as a bar series, not used alone.
2. Ex-ante gap (the real lineup signal). Each player's typical score is the
   median of their own earlier non-zero weekly scores in this league. We
   compare the starters with the best legal lineup by typical score, so
   "started a 4-point player over a 14-point player" counts and plain bad luck
   does not. Bench players who scored zero are assumed unavailable. Starters on
   a bye are not counted as mistakes by themselves.
3. Slot waste. Empty starting slots, zero-point starters, or bye starters
   while an eligible live player sat on the bench (slot eligibility honours
   FLEX, SUPER_FLEX, REC_FLEX, IDP flex).

Weekly severity = 0.6 x ex-ante (full at 25% below best typical) + 0.4 x slot
waste (full at a third of slots), or 0.8 x slot waste in early weeks with no
history. We subtract that week's league median severity (a rough week for
everyone is not a flag), multiply by the context factor, and flag the week at
0.30 or more.

Persistence. Flagged weeks, longest run, latest run. Fewer than 2 flagged
weeks caps persistence at 0.35, so a one-off never moves a band. Lineup score =
persistence x magnitude.

Roster and transaction behaviour (second, independent group):
- dropped a player who started for them in the last 3 weeks and was scoring;
- sold player value for picks (same buy/sell read as `team_trade_history`);
- gave away a lopsided two-party player trade (value gap in the "decline" or
  "hard" band of `trade_value_bands`);
- a very weak signal: no waiver/free-agent add all season (adds 0.10 only).

Context (standings). Certified elimination/clinch per week from exact win
bounds (same conservative rule as `playoff_simulator`). It scales the week:
eliminated + record-based draft order 1.0; eliminated + lottery 0.95; unknown
rule 0.9; still alive 0.85 (losing offers no benefit, so mismanagement or
inactivity is likelier); clinched 0.7 (resting is plausible). Context never
raises a clean team and also sets the interpretation text: possible tanking /
inactivity or mismanagement / resting. When most flagged weeks came before
elimination the card says so.

Score = 0.65 x lineup + 0.35 x roster.

## Bands (calm, non-accusatory)

| Band | Rule |
|---|---|
| Not enough weeks yet | fewer than 3 evaluated weeks |
| Lineup looks fine | otherwise |
| Worth a look | score >= 0.30 and >= 2 flagged weeks |
| Strong signals | score >= 0.55, >= 3 flagged weeks, >= 4 evaluated weeks, AND both groups corroborate (lineup >= 0.50 and roster >= 0.25) |

A lineup-only pattern is capped at "Worth a look", however extreme. Confidence:
high with 6+ weeks and corroboration, medium with 4+ weeks, else low. Every
flagged card lists the evidence lines and "Could be innocent" explanations.

## Extras

- Repeated trades worth a look (two managers, all trades between them; never
  scored when a trade has an unpriced asset or three teams). Draft picks are
  priced from the one canonical pick table the Trade Analyzer and History
  grades share (`trade_ideas.canonical_pick_identity_value`, round-level, mid
  slot; a past trade's exact slot is unknown). Three patterns, each capped at
  "Worth a look" unless noted, framed as a prompt, never an accusation:
  - `lopsided`: >= 2 trades between them where the same side wins on value
    (decline/hard band). 3+ is "Strong signals".
  - `round_trip`: >= 3 trades between them AND >= 2 assets (players or picks)
    that went back and forth between them, each return within 14 days of the
    previous move (value deltas cancel, so lopsided cannot see it).
  - `burst`: >= 3 trades between them in one in-season week (week 1 holds all
    offseason trades, so it never counts).
  Validated on real leagues (see PR): league 1312122984617476096 rosters 3 and 9
  (same picks moved back and forth across 3 trades) and 3 and 6 (3 trades in
  week 4, 3 assets returned) are now flagged; the other 3 public leagues stay
  clean.
- Possibly inactive: same starting lineup 4+ weeks in a row with no roster
  moves all season, or empty starting slots in 2+ weeks.

## Page layout and calendar

Default view for a clean league: one summary line ("All 12 teams look fine this
week") with a count and an expandable team list, instead of one green card per
team. The report also returns `calendar` (trade deadline, weeks left, phase,
playoff start week, current week) read from the league settings through
`modules/league_calendar.py`; web and app show it as a "League calendar" card.
Nothing is guessed: no deadline setting (Sleeper uses 99) shows "No trade
deadline set".

## Limitations (also returned in `limits`)

- Sleeper does not expose past injuries/inactives. We exclude bye weeks and
  zero-point players; a late scratch can still look like a mistake. The
  league-median adjustment and the persistence requirement are the guard.
- The draft-order rule is not published, so the user states it (page
  control, default "Not sure"); it only changes interpretation text and the
  context factor, not the lineup math.
- IR/taxi exclusion uses the current roster, not that week's.
- Greedy narrowest-slot-first lineup solving is optimal for nested flexes;
  overlapping custom flexes (WRRB with REC) may be off by a slot.
- Pick prices are round-level (same as the Trade Analyzer); trade value uses
  current values, not values at trade time.
- Results are cached 30 minutes per (league, draft rule).

## False-positive handling

Prompts, not verdicts: a team flagged because of a late injury, a thin
position, a bye conflict or a busy manager looks the same in saved data, so
each card lists those explanations and tells the reader to ask the manager first.
Tuning knobs are constants at the top of `modules/league_integrity.py`; the
golden synthetic leagues in `tests/test_league_integrity.py` (obvious tank,
injury-ridden innocent team, one-off bad week, post-elimination vs alive,
playoff-week exclusion, collusion pair, balanced/pick trades, inactive
manager) pin the behaviour.

## Trade veto calculator (outrage fairness, whole team)

Request (coridian_, 2026-11-04): "in the commissioner section we need a trade veto calculator for outrage
fairness that takes into account their whole team", plus: teams that are doing badly or have no future will
want youth and picks, which can lose market value and still be a good trade, so the logic has to account for it.

Engine: `modules/trade_veto.py` (pure scoring) + `trade_hub_engine.generate_veto_check` (data). Endpoint:
`POST /v1/leagues/{id}/commissioner/veto-check` with `{roster_a, roster_b, a_sends_player_ids,
b_sends_player_ids, a_sends_pick_ids, b_sends_pick_ids, lens}` (pick ids as in `GET .../draft-picks`). Same access
as the integrity view (Pro, any league the user can open; ESPN/MFL `unsupported_platform`).

Input is a PROPOSED trade between two current rosters (players and picks each team still owns). Sleeper does not
publish pending trades, so the commissioner enters the trade; completed trades are not re-graded (rosters have
moved since, so a re-grade would be wrong; the integrity view already flags lopsided completed trades).

### What it computes (nothing new is valued)

Per side, with that team's whole roster at that team's OWN auto posture (contender / retool / rebuild from the
rankings classification; a declared Team Situation is private to its owner, so it is not used here):

* `market_delta`: value received minus value sent (players at healthy value, picks at the Analyzer's pick price at
  that posture, so a rebuild prices picks and youth as a rebuild would).
* `team_score`: `roster_value_model.evaluate_swap` -> `trade_lineup_model.evaluate_trade` trade score: lineup
  points (slots, byes, injuries, depth, holes), plus the posture weights on now vs future value. A rebuilding
  team that sells a vet for youth or picks loses market value but can read fine here; that is the point.
* `points_per_week` and the worst position (where the hit lands).

Outrage (0-100) reads the side that comes out worst on `team_score`:

* team read within the "essentially even" edge (150): only 40% of the market gap counts (explainable);
* otherwise 60% market gap + 40% team gap, each normalised to the "hard decline" rung (2,200);
* repeat pattern: +6 per earlier lopsided trade the other side won from this team this season (max +15), only
  once the trade already reads 25+ and is not explained by the roster. History never turns a fair trade into a flag.

Bands: under 20 Fair; 20-44 Uneven but explainable; 45-69 Lopsided: worth a conversation; 70+ Outrage-level:
review before it processes. Weights, cutoffs and the 2,200 rung are judgment calls, not backtested.

### Limits (shown with every result)

Estimates from projections and the market; a manager may have reasons the numbers cannot see; a signal to look at
a trade, never proof of collusion; the league's rules decide. No free-agent pool is used for the lineup fill (a
league-wide pool per request is too heavy), so holes fill at market replacement level.
