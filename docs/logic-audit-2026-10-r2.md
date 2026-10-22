# Logic audit round 2 (October 2026)

Scope: hunt for places where one flat rule produces dumb advice, and for areas
round 1 (`docs/logic-audit-2026-10.md`) skipped. Method: real, unmocked engine
on synthetic leagues built from a throwaway copy of `players.db` (12-team 1QB,
Superflex and TE-premium), plus code reading of the decision paths. Real
public-league fixtures (`khook99`, `lukamagic777777`) were not run: the sandbox
has no network path used by the harness, so everything below is synthetic or
from code. Local FantasyCalc coverage is thin (many top players have a 0 FC
value locally), so FantasyCalc disagreements below are flagged as "check
production" rather than asserted.

## 1. Fixed in this round

| PR | Fix |
| --- | --- |
| #1419 | Team posture: the real-record weight had a 0.30 floor from game 1. A 90th-percentile roster fell Contender to Retool after one loss, and a median roster fell to Rebuild after week 1. The weight now ramps with games played (25% at 1 game, full at 4+). Same blend feeds pick-slot projections. |
| #1420 | Playoff odds: `clinched`/`eliminated` came from the sampled probability, so a team with a real 0.02% path showed "eliminated" and a team that could still be tied out showed "clinched". Now exact conservative bounds (win ceilings/floors, ties unresolved, division seeding); uncertified teams are clamped to [0.05, 99.95]. Season-over leagues stay exact. |
| #1421 | Weekly lineups ignored kickoff locks. After Thursday night they could bench a player who already played or start one locked on the bench. Started players in the real lineup keep their slot; started bench players are ineligible ("Game started", mobile "Locked" pill). |
| #1422 | Trade ideas were addressed to orphan teams (Sleeper `owner_id` null). Both partner loops now skip them. |

## 2. Findings not fixed, ranked by user impact

1. **No news-to-value link beyond Sleeper injury status** (area 6, large).
   `news_factor` is hard-coded to 0.0 in the valuation frame. A role change,
   trade, or suspension article raises an alert but never moves value or
   projection until Sleeper's own fields change. Weekly projections also have
   no injury/inactive input (round 1: 681 of 684 known-out players still got a
   mean 13.2). Fix size: large; needs an owner decision on which events may
   move values and by how much.
2. **K/DEF/QB streaming does not exist** (area 4, medium). Waiver Priority Adds
   treat kickers as "need only if you have none"; `_roster_has_viable_kicker`
   ignores bye weeks and matchup, so a kicker on bye is "viable". DEF is never
   a streaming target. Fix size: medium (bye + opponent-strength gate, reusing
   `nfl_schedule.team_defense_strength`).
3. **Superflex QB uplift is a flat x1.35 for every QB** (area 1,
   `league_value_settings.league_settings_adjustment_components`). A 38-year-old
   backup-grade QB (Stafford, FC 1QB value 1,468) lands at 6,622 in Superflex,
   above Chase Brown and Garrett Wilson. The market uplift is not flat: it is
   larger for mid-tier QBs than for elite ones, and the age curve is applied
   before the multiplier. Recommendation: scale the uplift by QB tier and
   age. Judgment call.
4. **Strategy age curves are step functions** (areas 1 and 9,
   `trade_hub_engine.apply_strategy_age_curve`, `rebuild_multiplier` in
   `apply_valuation_lens`). A rebuilding RB goes x1.00 at 27 to x0.82 at 28 (x0.75
   at 27 for a tank), stacking on a base age curve that already drops 11% from
   27 to 28. WR at 30, TE at 31, QB at 34 behave the same. Players flip in and
   out of Hub ideas on a birthday. Recommendation: interpolate over about two
   years. Weights are a product call.
5. **Manager Tendencies is not wired into acceptance odds, and should not be
   in this form** (area 5). The market-realism score uses the older
   `trading_style` / `asset_behavior` / `activity_level` labels. The newer
   evidence-based `modules/manager_tendencies` (labels such as `sells_picks`,
   `acquires_younger`, `consolidates`, `rebuilding`) is PRO-gated and costs a
   multi-season Sleeper scan on a cold cache; wiring it into Hub generation
   would make a Hub request pay that scan, change idea ranking by cache warmth,
   and leak a PRO signal into Free ordering. Recommendation: precompute it in
   the warm job, attach `tendency_signals` to each partner row, and add small
   bounded nudges inside `evaluate_trade_market_realism` only for signals with
   `status == "ok"`. Not done here because it needs a warm-cache decision.
6. **Stance ignores playoff odds, time-to-deadline and draft capital in the
   final label** (area 3). `refine_team_directions` blends starter, roster,
   bench, age, draft capital and health, but only the baseline carries the
   record, and refinement can move the baseline at most one step (two in
   extremes). A 0-6 team with an elite roster stays "Retool" at best; a 6-0
   mediocre roster stays "Fringe". That is reasonable, but the playoff-odds
   simulator and the trade deadline never enter. Recommendation: feed
   `playoff_probability` and weeks-to-deadline into the posture, behind the
   existing max-shift cap.
7. **Waiver drop list has no league-roster or best-FA comparison** (area 4,
   `app.py` drop scoring). It is multi-factor (value, role, handcuff, age,
   stash, position surplus), but flat weights (+72 unsigned, +42 FA-level
   veteran, -26 rookie stash, -30 developmental QB) are not compared with the
   best available free agent at that position, and the only thin-position
   guard is `need_flag` (-10). Starters and high tiers are protected, so
   dropping a lineup piece is unlikely; dropping the only backup TE/QB in a
   2-start league is possible. Judgment call.
8. **Priority adds use flat cutoffs** (area 4): `quantile(0.85)`, `rank <= 2`,
   soft cap of 2 per position, regardless of league size or roster spots.
   Roster-spot limits are used by Trade Hub (`roster_at_limit`) but not by the
   waiver list.
9. **Pick discount is a flat 0.88 per year** (area 2, `_pick_value_components`),
   the same for contenders and rebuilders and for 1.01 or 1.12. The strategy
   multiplier (x0.88 contender to x1.25 tank) is applied afterwards. Class
   strength is applied but only through crowd/prospect signals when available.
   Recommendation only.
10. **Cooling is a single threshold** (area 6): `recency_trend <= -0.12` with
    4+ games. It correctly damps moderate injuries and skips major ones, but it
    has no concept of a returning-from-injury partial game or game script.
    Fine as a principled constant today.
11. **Greedy lineup fill is not globally optimal** when slots overlap
    non-nested (WR/RB with REC_FLEX); rare. K and DEF have no weekly
    projection, so they rank by season value or the value-matched fallback.

## 3. Area notes

- **Values and tiers (1).** Top-100 ordering in 1QB, SF and TEP is sane at the
  top (Gibbs, Bijan, JSN, Puka, Chase). Age curves are position-aware and
  continuous. Absurd-looking cases are all explained by local FantasyCalc
  gaps: James Cook III (FC 0 locally, ranked 6th via market score), Kenneth
  Walker III, Aaron Jones Sr. (31, ranked 27th, FC 0), Chris Godwin Jr.
  (30, ranked 49th, FC 0). Check production coverage; round 1 already flagged
  that the fallback skips the age adjustment. TE premium behaves (Fannin and
  Pitts rise, QBs unchanged). Superflex: see finding 3.
- **Draft Center and picks (2).** Spent-pick handling and next-draft years are
  correct on the real path. Pick values by round and slot look sane (2027 R1
  early 6,737, late 4,746). No bug found; see finding 9.
- **Stance (3).** Several factors are used. The week-1 flip was the real bug
  (fixed). Hysteresis is absent: a team at a percentile boundary can still flip
  on a small roster change. Recommendation: require a margin to leave the
  current label.
- **Waivers (4).** FAAB was redesigned and is out of scope; see findings 2, 7, 8.
- **Trade ideas (5).** Re-running the Hub on a synthetic Superflex league
  shows the Hub and Analyzer now agree (the round 1 DECLINE mismatch is gone).
  Most ideas carry Low confidence because synthetic rosters are uniform. Orphan
  partners fixed; there is still no "dead manager" filter (an owner with no
  activity all season is an equally valid-looking partner).
- **Alerts (6).** See finding 1. Alert dedupe and supersession logic exist in
  `news_intelligence`; not exercised here.
- **Start/sit (7).** Bye, Out and IR handling is solid in weekly mode, and the
  kickoff lock is now covered. K and DEF fall back to value-matched estimates.
- **Playoff odds (8).** Divisions and median games were fixed in #1372;
  clinched/eliminated fixed here. Remaining gaps: the points-for tiebreak is a
  static proxy, the logistic slope is fit from few games early, and head-to-head
  tiebreakers are not modeled.
- **Single-factor shortcuts (9), worst offenders.** (a) Step-function strategy
  age curves; (b) flat Superflex QB x1.35 and 2QB x1.55; (c) flat `0.88 ** years`
  pick discount; (d) flat `top 15%` / `rank <= 2` waiver cutoffs; (e) flat
  +/-points in the drop score; (f) the market-realism score starts at 58 and
  adds fixed increments per heuristic (+8, -12, -22 ...), none scaled to league
  size or settings; (g) fixed `ones.clip(0.35, 2.2)` league multiplier cap.

## 4. Not tested

Real public leagues for the two named users, production FantasyCalc coverage,
the Streamlit web drop-candidate path end to end (code read only), live
Sleeper `starters` payloads for the new kickoff lock (covered with unit tests and
the mocked mobile world), mobile typecheck (no `node_modules` in the worktree;
the node unit test for the label helper passes).
