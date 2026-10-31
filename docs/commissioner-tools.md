# Commissioner tools: League integrity

Request (coridian_): "a commissioner section where you can see if teams are
purposefully tanking and stuff". Engine: `modules/league_integrity.py` (pure,
testable). Data gathering and cache: `modules/league_integrity_data.py`.
Endpoints: `GET /v1/leagues/{id}/commissioner/status` and
`.../commissioner/integrity?draft_order=unknown|record|lottery`. Web:
`/commissioner/[leagueId]`. App: `Commissioner` screen. Shared presentation:
`lib/commissionerIntegrity.ts` (SHARED block byte-identical on web and app,
checked by a mobile test).

## Who sees it (honest limit)

Sleeper's public league users list marks the commissioner(s) with
`is_owner: true` (verified against a public league: several co-commissioners
can carry it). The server matches that to the signed-in user's own roster
owner. Only then does the nav entry appear (web sidebar and GM Orb, app GM
Orb) and the integrity endpoint return data. Everyone else gets reason
`not_commissioner` and no teams. We deliberately did not offer a read-only
view for every member: tanking accusations about named managers belong with
the person who can act on them. ESPN/MFL/other imported leagues are not
supported (`unsupported_platform`). Tier: Pro, like Playoff Odds and the other
advanced league tools (`_is_pro_caller`; trialing counts as Pro). The status
check is ungated so a Free commissioner still sees the entry and the upsell.

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

- Repeated lopsided trades: two managers with >= 2 trades between them where
  the same side wins on value >= 2 times ("Worth a look"; 3+ is "Strong").
  Trades with picks, three-team trades and unvalued players are never scored.
- Possibly inactive: same starting lineup 4+ weeks in a row with no roster
  moves all season, or empty starting slots in 2+ weeks.

## Limitations (also returned in `limits`)

- Sleeper does not expose past injuries/inactives. We exclude bye weeks and
  zero-point players; a late scratch can still look like a mistake. The
  league-median adjustment and the persistence requirement are the guard.
- The draft-order rule is not published, so the commissioner states it (page
  control, default "Not sure"); it only changes interpretation text and the
  context factor, not the lineup math.
- IR/taxi exclusion uses the current roster, not that week's.
- Greedy narrowest-slot-first lineup solving is optimal for nested flexes;
  overlapping custom flexes (WRRB with REC) may be off by a slot.
- Pick values are not priced; trade value uses current values, not values at
  trade time.
- Results are cached 30 minutes per (league, draft rule).

## False-positive handling

Prompts, not verdicts: a team flagged because of a late injury, a thin
position, a bye conflict or a busy manager looks the same in saved data, so
each card lists those explanations and tells the commissioner to ask first.
Tuning knobs are constants at the top of `modules/league_integrity.py`; the
golden synthetic leagues in `tests/test_league_integrity.py` (obvious tank,
injury-ridden innocent team, one-off bad week, post-elimination vs alive,
playoff-week exclusion, collusion pair, balanced/pick trades, inactive
manager) pin the behaviour.
