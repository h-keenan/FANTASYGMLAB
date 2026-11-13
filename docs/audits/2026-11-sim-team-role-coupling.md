# Sim team-role coupling and the double-counted backup (2026-11)

Report: in the Fantasy Sim GM game's Players tab, free agents Joe Milton and Tanner McKee (PHI QBs, Jalen Hurts out) both showed
starter-level projections (14.6 and 13.5), although only one backup starts. Same shape for any team with an injured starter.

## TLDR

- **Root cause (display).** The sim's player pool (`modules/sim/inputs.py` `RealSimInputs.player_pool`) takes each player's projection from
  `player_projections.baseline_weekly_points`. That is a per-player, usage-based estimator over his own recent games, with **no role layer and
  no availability layer** by design (its docstring says so: "the trade lineup model handles byes and injuries itself"). A backup who started
  while the starter was out carries that "if he starts" number whether or not he will start. Each backup is computed independently, so a team
  with a hurt starter and two backups shows two starters. Nothing in the real logic "gives each backup the starter's share"; the double count is
  the sum of independent if-he-starts numbers, and the sim then used those numbers as the means it simulates.
- **Root cause (scoring).** `modules/sim/player_model.py` draws every player independently and `apply_depth_coupling` (the calibrated backup
  uplift) was never wired into the engine, so with both backups healthy the sim scored both at roughly 13 to 14 points in the same week, about
  27 QB points for one NFL team, and again when the real starter returned.
- **Fix (new games only, `player-model-3`).** Team-level role coupling resolved per NFL team, position group and week
  (`modules/sim/team_roles.py`, pure and deterministic): one fill-in per vacated starter, everyone else stays at baseline. Scoring, AI lineups,
  waivers, valuations and the Players/waiver/draft "Proj" all use the same resolved roles. Old saves are untouched (frozen `player_model_v2.py`).
- **Real app.** Not affected on the player-facing projection path; affected on the baseline-only paths. Details and recommendation below.

## 1. Mechanism, with the data that triggered it

`data/players.db` (read-only), PHI QBs at the time of this audit:

| QB | depth_chart_order | status | ppg (own recent games) | games |
| --- | --- | --- | --- | --- |
| Joe Milton | 1 | Active | 13.16 | 1 |
| Jalen Hurts | 2 | IR | 16.60 | 5 |
| Tanner McKee | 3 | Active | 10.71 | 3 |
| Cole Payton | 4 | Active | 0.0 | 1 |

Both Milton and McKee have a ppg from games they played while Hurts was out. The pool turns each into a mean (`mean = baseline ppg`) and an
injury of 4 weeks for the injured (`injury_weeks = 4` when `injury_status` is out/IR). Nothing couples McKee to Milton. Note the live Sleeper
depth chart lists the injured Hurts second, below his fill-in: the chart is a snapshot that already demotes an injured starter, so it cannot be
used alone to say who starts when he is back.

Other pools with the same shape today: BAL (Lamar Jackson IR 16.0, Huntley IR 11.1, Brissett 14.8), SEA (Lock 15.6, Darnold Out 14.5),
WAS (Daniels 19.2, Mariota 11.5, Kaliakmanis Out 12.0), NYG (Dart IR 13.7, Winston 11.2, McCarthy 8.7), MIN (Cousins 20.0, Wentz 8.3,
Murray 12.8).

## 2. The coupling (what `team_roles.py` does)

Per NFL team and position group (QB, RB, WR, TE), each week, from public information only (current injuries and byes, never the hidden season
profile; `Evaluator.status` is the single source, so scoring and display agree and resume == replay):

1. **Depth order**: `depth_chart_order` when present, else projection. A star who starts the season injured (the highest-market player of the
   group) keeps the top spot, because live charts demote the injured starter below his fill-in but he starts when back.
2. **Depth starters**: the first QB 1 / RB 2 / WR 3 / TE 1. Each one who is out (or on bye) vacates a slot.
3. **Exactly one next-in-line healthy non-starter inherits each vacated slot**, in depth order. Others stay at baseline.
4. **Uplift is the calibrated one** (`InSeasonParams.absorb` of player-model-2/3: QB 0.6, RB 0.33, WR 0.23, TE 0.10, a test pins equality):
   - QB: single-role position. The one who plays gets `0.2 x own mean + 0.6 x the starter's mean` (Milton: 0.2 x 14.6 + 0.6 x 17.0 = 13.1, about
     his own if-he-starts number). Every other healthy QB behind the playing QB is a bench QB at 0.2 of his mean (the same prior the real
     projection uses, `BACKUP_QB_PLAY_SHARE`), so McKee shows about 2.7 instead of 13.5.
   - RB/WR/TE (committees): the inheritor gets his own mean plus `absorb x 0.8` (the first backup's share of the 4 : 1 split used by
     `apply_depth_coupling`) of the vacated starter's mean. Other backups unchanged. Partial by design.
   - K and team defenses: exempt (multiplier 1).
5. A returning starter restores roles automatically (the next week's resolution sees him available). A new injury re-resolves the following
   weeks the moment the engine records it.

Engine wiring: `ScoringSession.week(pid, week, role_mult)` hands the multiplier to the model, which applies it as a one-week `RoleChange`
(`player_model.with_role_multiplier`, no extra random draw). The Evaluator carries the same roles: `proj`/lineup entries use the week's role,
`ros_mean` (valuations, waivers, AI lineups, power rankings) is the base mean times the average role over his playable weeks left, so a
four-week fill-in is not valued as a starter, and a stash of both backups is not rewarded.

Displayed projection ("Proj" in Players, waivers, draft board, roster rows): expected per-game points for the **next game he can play**,
role-resolved. McKee shows his backup number; Milton the fill-in number while Hurts is out; Hurts shows his own number (he is "Out", the
chip says so). Role chips: "Starting while Hurts is out" (QB) / "Filling in for X" (RB/WR/TE) / "Backup". The player sheet adds
"If he starts: N pts" (the old role-free number). The signed-out preview list uses the same week-1 roles.

Draft value and ADP are computed from the same pool means as before (`value_pool` is unchanged), so a backup's ADP and his shown projection do
not contradict each other through a second adjustment. Known limit: a backup QB's VORP still reads his if-he-starts mean (it is small against
the replacement level, and the market half of the value blend is role-free); not changed here.

## 3. Versioning and replay safety

- New model id `player_model-player-model-3`. `modules/sim/player_model_v2.py` is a frozen byte copy of player-model-2 (sha256 pinned);
  `player_model.py` is v3 (same draws, `TEAM_ROLES = True`, `with_role_multiplier`).
- Games created before this change keep `player_model-player-model-2` (or `-1`, or the fallback id), never receive a role multiplier, and
  their Evaluator behaves exactly as before. Golden state digests for a v2 game (weeks 2-6, seed 11) were produced by the pre-change code and
  are pinned in `tests/test_sim_game_model_versions.py`.
- No settings flag is needed: the model id is the gate (`game_scoring.team_roles_enabled`).

## 4. The real (non-sim) app

Checked `modules/player_projections.py`, the real waiver/players surfaces and the other consumers of the baseline:

- **Per-player projection (`project_player_week`, behind the players list, player pages, waivers): no double count for QBs.** It has a role
  layer (`_role_adjustment`, `BACKUP_QB_PLAY_SHARE = 0.2`: a QB the depth chart lists behind a healthy starter is multiplied by 0.2) and an
  availability layer (`injury_status`). On the PHI rows above it returns: Milton 1.0 (depth 1), McKee 0.2 (behind healthy Milton), Payton 0.2,
  Hurts 0.2 and then zero through availability. One fill-in, one backup: the intended behaviour.
- **Not covered: RB/WR/TE.** No role layer. A backup's baseline is his own recent usage, which is correct while the starter is out (it is
  actual usage) and stale after the starter returns. This is the staleness the sim coupling models; it is not a double count of one week's
  volume, so no silent change.
- **Baseline-only paths do carry the sim's problem.** `baseline_weekly_points` (no role layer, no availability layer) feeds
  `modules/trade_grade.py` (the roster-aware lineup model) and `modules/weekly_roundup.py`. For a roster that holds a hurt starter's two
  backups in a superflex or 2-QB lineup, trade grade can see two starter-level QBs where one will play. Whether this matters in practice depends
  on how those callers add their own availability; I did not trace every caller and I did not change them.
- **Recommendation (separate, tested PR; not done here because it moves real valuations):** apply `_role_adjustment` (QB) inside
  `baseline_weekly_points` for callers that do not apply their own role handling, behind a keyword so the sim pool and existing goldens keep
  the current numbers; add a depth-chart role layer for RB/WR/TE only after a walk-forward test (R-series findings in
  `2026-11-sim-projection-audit.md` section 3.2 describe the harness). Verdict: not a clear bug in the player-facing projection, a gap in the
  baseline-only paths. **No real valuation logic was changed.**

## 5. Tests

`tests/test_sim_team_roles.py`: one fill-in per vacated starter (QB, RB, WR), starter returns, second backup falls back, mid-season injury
re-resolution including a hurt fill-in, K/DEF exempt, depth order and the returning-star rule, determinism and order independence,
resume == replay on a new game, old-model saves never see a multiplier and match their golden digests, pool means (draft value/ADP) unchanged
between model ids, team QB points near one starter not two (v2 versus v3 over four seeds), AI valuation and lineup entries use the resolved
roles, constants pinned to the calibrated absorb table and the real backup-QB prior. Plus the frozen-v2 hash and golden digest tests.
