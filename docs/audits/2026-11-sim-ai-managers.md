# Sim AI managers: byes, injuries, the wire (2026-11)

Ask (coridian_): "make sure the AI takes into account bye weeks and uses the waiver wire so they have backups throughout the year."
Shipped as AI generation 1 (`GameSettings.ai_v = 1`, new games only; `ai_v` absent/0 = the AI as it was, replays identically).

## What the old AI did (ai_v 0)

One claim per team per week, only when a slot was empty THIS week (an "emergency") or a random roll passed. Lineup value ignored byes
and unannounced injuries, drops were limited to a narrow "kept" rule, a trade could open a hole after claims had run, and nothing
bought insurance at a position with no backup. Result: 4% of AI team-weeks started with an empty slot, only about half of rosters could
absorb one injury at every core position, and kickers/TEs on bye regularly went uncovered.

## What ai_v 1 does (`modules/sim/game_ai_depth.py`, pure, deterministic)

One roster value, computed from the manager's own team parameters:

`value(roster) = sum over the next 3 weeks (weights 1, .6, .3) of best-lineup total with byes and known injuries applied week by week
 + INSURANCE x sum over core positions of slots x best backup's mean`

- **Claims**: the free agent whose addition raises that value most, scored with the same need / horizon / worth blend as before. A hole this
  week or next (a bye, a known injury, a trade) is an emergency: the random gate and the bar are waived and up to 3 claims go in
  (waiver order, the wire is shared, so a free agent another team took is gone). A free roster spot at a position with no healthy
  backup is just filled (up to 2). Routine upgrades still pass the persona's gate (waiver_aggr) and bar.
- **Drops**: the player whose removal costs that value least, then his long-run worth; never this week's starters, never the only K/DEF.
- **No hoarding**: a position holds its slots (plus flex share) plus 1-2 backups (K and DEF: one unless a bye needs cover).
- **Trades**: after the week's AI-to-AI trades, any team with a hole picks up cover before lineups lock (`_post_trade_cover`). The trade
  desk itself (including the #1838 counter rules) is unchanged and was not re-tuned.
- **Offseason (dynasty)**: `_fill_holes` also gives every core position a healthy backup (`depth_adds`); roster cut-down
  (`enforce_roster_cap`) cuts by marginal cost to the next weeks' lineups, then worth, not worth alone. The AI rookie draft board
  is unchanged (it already weighs need). There are no contracts in the sim, so "re-signing depth" is the depth fill above.
- **Feed**: waiver rows say why ("added X to cover a bye / an injury / for depth").

Versioning: `ai_v` is stored in settings (serialized only when non-zero, so old saves serialize as before); every branch is
`settings.ai_depth`. Goldens: v1/v2/v3 state digests (taken before this change) still match with `ai_v=0`; ai_v 0 and ai_v 1 digests on
player-model-4 are pinned in `tests/test_sim_ai_managers.py`; `game_ai_depth.py` is on the isolation test's pure list.

## Numbers (`python -m modules.sim.calibration.ai_report`; AI teams only, regular season)

Redraft: 12 teams, pool built from the real 2025 panel, 8 games (about 1,170 AI team-weeks). Dynasty: 8 teams, 3 seasons, synthetic pool, 3 games.

| metric | redraft ai0 | redraft ai1 | dynasty ai0 | dynasty ai1 |
| --- | --- | --- | --- | --- |
| starting slots empty (share of slots) | 0.49% | 0.15% | 0.56% | 0.06% |
| team-weeks with an empty slot | 3.8% | 1.2% | 4.2% | 0.5% |
| rosters with a healthy backup at QB/RB/WR/TE | 55% | 76% | 35% | 71% |
| starter scored exactly 0 (played) | 2.0% | 2.0% | 1.2% | 1.0% |
| adds per AI team per season (mean / p90) | 7.1 / 10 | 5.8 / 9 | 4.4 / 10 | 4.4 / 10 |
| roster size mean / max | 15.2 / 16 | 15.0 / 16 | 15.5 / 16 | 15.6 / 16 |
| team-weeks with a position over (slots + flex + 3), or 3+ K | 16% | 4% | 52% | 20% |
| max QB / RB / WR / TE / K held | 6/10/10/7/2 | 4/8/9/4/3 | 9/11/10/9/3 | 7/10/8/6/2 |
| add-then-drop-again within 3 weeks | 10 | 6 | 4 | 3 |
| waiver adds / drops / trades (all AI) | 622 / 119 / 29 | 512 / 97 / 33 | 277 / 51 / 28 | 274 / 51 / 39 |

Reading: empty slots and uncovered byes drop by 3-8x; depth cover up 21-36 points; fewer, better-targeted adds, no hoarding, rosters never exceed
the limit. What is left of the empty slots is scarcity (a league that has run out of free quarterbacks), not planning. A "0-score starter"
is mostly a TE/WR/K variance game (the real rate for starters is similar), so it does not move. Dynasty still holds more WR/TE than redraft
because rookies and taxi prospects are kept for value, not claimed off the wire. K adds stay about a quarter of all adds: every kicker has a
bye and a second K for that week is the same call a human makes; the extra K is the first player cut afterwards.

## Not done

- The trade desk does not value depth or byes beyond the lineup utility it already had.
- FAAB: the game uses waiver priority (worst record first, resolved at Advance), so there is no bidding to model.
