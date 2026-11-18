# Advice handshakes audit (2026-11-18)

Goal (product owner): every piece of advice should be informed by everything
we already know about our roster, every other team, and the deep analytics.
Example: roster ages should reach trade advice; other teams' pick portfolios
should reach trade ideas.

Scope: read-only code audit of `origin/main` at `c8513d5e`. No data files
were read or written. Line numbers are as of that commit. Where I could not
fully confirm a claim it says "verify".

Legend for the matrix: **Y** = consumed in decisions, **P** = partial (words
only, coarse flag, or one path of several), **-** = not consumed, **n/a** =
not meaningful for that surface.

---

## 1. Signal inventory

### 1a. Our roster

| Signal | Computed at | Notes |
|---|---|---|
| Player age | `player_universe.resolve_age` `modules/player_universe.py:127`; team ages `team_eval.known_player_ages` `modules/team_eval.py:82`; team avg `team_eval.py:841` | Birth-date based, placeholder 99 dropped |
| Age curve (per position) | `rankings.AGE_CURVE_CONTROL_POINTS` `modules/rankings.py:141`; `age_multiplier` `:1005`; `prime_window_for_position` `:1060`; baked into dynasty value via `age_curve_score` `:3851`, weight `COMPOSITE_WEIGHT_AGE` `:76` | The one real, calibrated curve |
| Strategy-shaped age curve | `trade_hub_engine.apply_strategy_age_curve` `modules/trade_hub_engine.py:72`; pick multiplier `_PICK_STRATEGY_MULTIPLIERS` `:175` | Rewrites the score field per posture |
| Future-year aging | `trade_lineup_model._aged` `modules/trade_lineup_model.py:886` | Uses `rankings.age_multiplier` (good) |
| Positional depth, need, surplus | `roster_value_model.assess_needs` `modules/roster_value_model.py:776`, `league_needs` `:1006`; adapter `roster_needs.assessment_from_model` `modules/roster_needs.py:174`; K/DEF `true_shallow_position_needs` `:390` | The canonical need model, one table for the league |
| Posture / stance (declared) | `team_stance` `modules/team_stance.py` (3 states); lossy map `team_strategy_for_stance` `:142` | Per user per league, Supabase |
| Posture (resolved, for me) | `trade_hub_engine.roster_posture` `modules/trade_hub_engine.py:906` -> `trade_posture.resolve_posture` `modules/trade_posture.py:175`; mobile wrapper `_resolve_trade_posture` `services/mobile_api_service.py:6452` | declared > auto > client, with confidence |
| Posture (auto, every team) | `team_eval._classify_team_strategy` `modules/team_eval.py:202` (value percentile blended with record + age delta) | 5 states |
| Window assessment | `trade_posture.assess` `modules/trade_posture.py:268` (lineup-model win-probability per point) | Contender/rebuild fit of a trade |
| PQV (player quick view) | `player_quick_view.build_executive_snapshot` `modules/player_quick_view.py:81`; OVR `overall_ratings_for_pool` | Presentation layer; reads the curve, adds nothing back |
| Injuries | `injury_status.classify` `modules/injury_status.py`; `rankings.injury_multiplier_for_age` `modules/rankings.py:2687`; `rankings.summarize_team_injuries` `:3233`; `trade_analyzer_fit.roster_injury_context` `modules/trade_analyzer_fit.py:347` | |
| Byes / schedule | `nfl_schedule.team_bye_week` `modules/nfl_schedule.py:291`; `bye_cover` `modules/bye_cover.py`; `trade_lineup_model._bye_for` `:455` | |
| Depth chart | `depth_chart_history` `modules/depth_chart_history.py`; `player_depth_chart` | Display + `roster_value_model` depth |

### 1b. Every league team

| Signal | Computed at | Notes |
|---|---|---|
| Ages (team avg, age rank) | `team_eval.build_league_summary` `modules/team_eval.py:749` (avg_age `:841`), `age_rank` via `league_rankings` | |
| Needs / surplus | same `roster_value_model.league_needs` (all rosters at once, `:1006`) | Shared and memoized |
| Posture | `team_eval._classify_team_strategy` `:202` (base), `refine_team_directions` `:1347` (archetype refine, see section 3) | |
| Pick portfolio | `trade_ideas._build_roster_pick_assets` `modules/trade_ideas.py:681`, `list_draft_pick_assets` `:861`; team rollup `league_rankings.build_draft_capital_summary` `modules/league_rankings.py:67`; `_draft_profile` `trade_ideas.py:2655` (tier, firsts) | |
| Projected pick slot | `trade_ideas._pick_team_context` `:316` (roster value percentile blended with record via `record_signal.blend_percentile_with_record` `modules/record_signal.py:118`); `_projected_pick_slot` `:667` | Slot model is roster value + record only |
| Pick-flow (1sts bought/sold) | `pick_flow.league_pick_flow_counts` `modules/pick_flow.py:34` | Display badge only |
| Trade tendencies (simple) | `team_trade_history.league_trade_tendencies` `modules/team_trade_history.py:130` (buyer/seller by leg counts) | Display badge |
| Trade tendencies (rich) | `manager_tendencies.build_league_tendencies` `modules/manager_tendencies.py:594` (multi-season, evidence ids, min samples) | Premium-gated display; docstring says "Not wired into trade recommendations yet" |
| Activity / streaks | `manager_activity`, `team_streaks` | Display badges |
| Playoff and title odds | `playoff_simulator.simulate_playoff_odds` `modules/playoff_simulator.py:377`, `build_league_playoff_odds_cached` `:965`, `team_odds_row` `:661` | Only GM Plan + odds screens read it |
| Opponent read (rooms, angle, pick capital) | `opponent_profile` `modules/opponent_profile.py` (`room_reads` `:90`, `trade_angle` `:171`, `pick_capital` `:226`) | A second, rank-based need/surplus engine, see section 3 |

### 1c. Deep analytics

| Signal | Computed at |
|---|---|
| Projections (weekly, ranges) | `player_projections.project_player_week` `modules/player_projections.py:1676`; calibration `projection_calibration.py`; `start_sit_range.range_for` `modules/start_sit_range.py:55` |
| Usage / target-share trends | `usage_trends.profile_for_player` `modules/usage_trends.py:386`, `profile_from_season_stats` `:597`, `role_change_line_for_player` `:467`; nflverse advanced stats `nflverse_advanced_stats.py` |
| Dynasty values | `rankings.build_players_table` `:4599` (composite: market .44, age .18, production .12, scarcity .10, role .06, opportunity .10, `rankings.py:75-80`); `fantasycalc.get_dynasty_values` `:37`; `public_dynasty_values.py`; lens via `league_value_settings` |
| ADP / rookie ADP | `rookie_adp.build_rookie_board` `modules/rookie_adp.py:559`, `value_vs_adp` `:515`, `estimate_sf_adp` `:638`; live-draft ADP delta `live_draft.py:360-398` |
| College prospects / class strength | `college_scouting.crowd_class_strength_by_year` `modules/college_scouting.py:220` (feature-flagged, `class_strength_signal_enabled` `:63`); `college_prospect_ingest.py`; prospect draft round `draft_capital.draft_round_for` `modules/draft_capital.py:60` |
| News / value events | `news_value_events` (feeds `rankings`), `news_intelligence`, `signal_corroboration` |
| Trade outcome history | `trade_outcome_results` `modules/trade_outcome_results.py` (did a confirmed trade work), `decision_log`, `verdict_feedback` |
| Decision memory | `decision_memory`, `decision_change_history`, `recommendation_lifecycle` (change history of recommendations) |
| FAAB / wire | `faab.py`, `waivers_logic.shared_waiver_adds` `modules/waivers_logic.py:481` |

---

## 2. Consumption matrix

Columns are signals; rows are advice surfaces. Evidence for each cell is in the
notes below the table.

| Surface | Roster ages / curve | Posture (mine) | Posture (others) | Needs / surplus | Other teams' ages | Pick portfolio / slots | Tendencies | Usage / projections | Injuries | Byes | ADP / college | Outcome memory |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Trade Ideas / Hub / Finder | P (asset-level only) | Y | Y | Y both sides | **-** (computed, unread) | P (tier + own/partner picks, one slot model) | **-** | P (overflow/drops only) | Y | P (via lineup model) | P (college class strength in pick price) | **-** |
| Trade Grade / Analyzer | Y (lineup model aging) | Y | P | P | - | P | - | P (role notes) | Y | Y | - | - |
| Shop / target offers | P | Y | P | Y | - | P | - | - | - | - | - | - |
| Multi-team trades | Y (per-team curve) | Y (own seat declared) | Y (auto) | Y | - | **-** | - | P (usage guard) | - | - | - | - |
| GM Plan | **-** | P (3-state declared only) | - | **-** | **-** | **-** | **-** | - | P | **-** | - | - |
| Today / dashboard | **-** | Y | n/a | Y | - | - | - | P (value trend) | Y | Y | - | - |
| Waivers | P (hardcoded cutoffs) | Y | n/a | Y | n/a | n/a | - | P (usage guard) | Y | - | - | - |
| Lineup / start-sit | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Y (projection range, win prob) | Y | Y | n/a | n/a |
| Draft room / live draft | P (hardcoded peak ages) | **-** (never fed, see notes) | - | P (separate coarse model) | - | P (pick pricing via trade engine) | - | - | P | - | P (ADP yes, rookie board separate) | - |
| Sim AI GMs | Y (own age curve) | Y (buy/sell) | Y | Y (own report) | - | Y (own slot model) | **-** (no memory) | Y | Y | Y (cover) | Y (ADP) | - |
| Notifications | - | Y | n/a | Y | - | - | - | - | Y | Y | - | - |
| External API | P (neutral) | n/a (neutral by design) | n/a | n/a | - | P | - | Y (projections) | Y | - | - | - |

### Notes with evidence

**Trade Ideas / Hub / Finder**
- Team shape is built at `trade_ideas._build_team_shape` `modules/trade_ideas.py:2938`. It stores `avg_age` and `league_age_mean` (`:3048-3049`), but the only read of them is the cache signature (`:2802`). No decision uses a team's average age. Ages enter only through the assets in a specific package: `_asset_avg_age` `:1521`, strategy fit `:4150-4163`, partner age fit inside `partner_acceptance_context` `:1886` (hardcoded 28 / 25 / 24 / 30 cutoffs).
- Partner posture and needs are read (`partner_acceptance_context` `:1886`, partner shape `:5232`). Recent PRs #2116/#2117 added mutual acceptability and the partner reason on the card.
- Partner pick portfolio is read only as a tier (`draft_capital_tier`, `:2677`; used `:4146`, `:4303`) and as the partner's pick assets for packages (`:5448`). No use of the partner's projected slots, pick flow, or whether the partner "wants" picks given their roster age.
- Pick price uses the user's posture lens for both sides (`strategy_adjusted_pick_score_multiplier` `trade_hub_engine.py:184`), so a rebuilding partner's own pick valuation is not modeled.
- Tendencies: `trade_ideas.py` imports neither `manager_tendencies` nor `team_trade_history`. Only `services/mobile_api_service.py` imports them (display, `:2851-2990`, `:3190-3205`).
- Usage trends reach `trade_ideas` only for drop candidates (`:4658-4670`).
- Trade outcomes, decision memory and verdict feedback are not read anywhere in idea generation.

**Trade Grade / Analyzer / Shop** - `trade_grade.py` (posture, injuries), `trade_offer_analyzer.py` (posture, counter bands `:341`, `:473`), `trade_lineup_model.py` (aging `:886`, byes `:455`), `trade_target_offers.py`. Role-change notes are added for Pro (`mobile_api_service.py:7086`, `:7923`). Partner-side acceptability in the Analyzer is limited to counter-package logic (verify whether partner posture is read).

**Multi-team** - each participant is graded through its own posture and age curve (`multi_team_trade_engine.py:334-340`), uses the shared need table (`:237`), untouchables, and the usage guard (`mobile_api_service.py:7190-7240`). It ignores pick slots, tendencies, and other teams' ages.

**GM Plan** - `gm_plan.build_gm_plan` `modules/gm_plan.py:536` takes the raw declared 3-state stance (`:536-588`), a rankings row, record, playoff odds, injury context, and trade ideas. The module docstring explicitly says it never reads the age-curve/strategy system (`:11-20`). The caller does resolve a full posture for the trade ideas (`mobile_api_service.py:14462`) but passes only the declared stance to the plan. No ages, needs/surplus, picks, tendencies, waivers, byes.

**Today / dashboard** - `dashboard_engine.py` has 79 posture/strategy references (e.g. strategy-check tile `:296` compares declared vs auto), league needs (`:695`), byes via `bye_cover`, trade tile `:396`, waiver tile `:180`. It has zero age references and one pick reference.

**Waivers** - posture lean (`waivers_logic.posture_lean` `:280`), need model (`:514`, mobile `:17700`), injuries/availability, usage guard (`mobile_api_service.py:17552`), FAAB. Age is used through hardcoded cutoffs (24 / 29 / 31, `waivers_logic.py:338-432`), not the curve. Other teams' needs and wire competition are not read.

**Lineup / start-sit** - projections with typical-week range and win probability (`start_sit_range.py`), optimal lineup `team_eval.suggest_optimal_lineup` `:585`, byes and injuries, role line (`mobile_api_service.py:15884`). Posture/age/picks are not relevant to a weekly decision.

**Draft room** - `live_draft._strategy_name` `modules/live_draft.py:643` reads `team_strategy` / `strategy` / `team_direction` from league settings, but nothing populates those keys (`mobile_api_service.py:5065` passes the detected settings dict), so the draft hint's age adjustment (`_age_strategy_adjustment` `:652`) always runs with "balanced" (verify with a runtime check; the grep found no writer). Needs use a separate coarse count model (`live_draft.roster_position_needs` `:484`, called `:553`, `:732`, `:1122`) rather than `roster_value_model`. Peak ages are hardcoded (`:658`). Draft-pick trades use the shared pick engine (`live_draft_trade_evaluator.py` docstring, `:1-30`) with a static fallback chart. The rookie ADP board is separate (`mobile_api_service.py:4101`, `:5101`).

**Sim AI GMs** - self-contained universe (`modules/sim/`): persona `TeamParams` `personas.py:12`, buy/sell posture `game_posture.py:40-106`, needs `game_need.position_report` `:20`, aging `aging.py:103-140`, pick slot `game_eval.pick_slot_frac` `:481`. There is no AI memory of past trades or a counterparty profile (no history/memory references in `game_ai.py`).

**Notifications** - `push_triggers.py` resolves posture (`:756`), the league need table (`:1134`), bye-week starters (`:1034`), untouchables. `notification_decider.py` is a thin dedupe/priority layer. No age, pick, or partner signals.

**External API** - `external_interesting_trades.py` deliberately values at the neutral strategy (`:55`, `:150`); projections endpoints (`mobile_api_service.py:10481`). Neutral is correct here (no user context), but it could use the real owners' postures to flag "interesting".

---

## 3. Duplicates and inconsistency risks

| Concept | Implementations | Risk | Canonical |
|---|---|---|---|
| **Posture (contender vs rebuilder)** | (1) `team_eval._classify_team_strategy` `:202`; (2) `team_eval.refine_team_directions` `:1347`, applied only in `mobile_api_service.py:2834`, `:4242` and `dashboard_engine.py:1184`, not in `league_rankings.build_league_rankings_frame`; (3) declared 3-state `team_stance` with lossy map `:142`; (4) `gm_plan` uses the raw 3-state; (5) `waivers_logic.posture_lean` `:280` collapses to contend/rebuild; (6) `live_draft._strategy_name` `:643`; (7) `manager_tendencies._posture_points` `:530` (behavioral); (8) `trade_posture.assess` `:268` (window) | The posture driving trade/waiver math comes from the *unrefined* rankings frame (`trade_hub_engine.roster_posture` reads `strategy` from `build_league_rankings_frame_cached`, `:936-944`), while League screens and the dashboard show the *refined* label. A team can be "Contender" in the math and "Retooling" on screen. Partners in trade ideas also use the unrefined summary strategy (`trade_ideas.py:2975`). GM Plan ignores the 5-state. | One `resolve_posture` result (`trade_posture.py:175`) for every team (declared only for the user), with the refine layer applied once, upstream, so every reader sees the same key. |
| **Age curves / age cutoffs** | Calibrated curve `rankings.py:141`; strategy curve `trade_hub_engine.py:72`; `league_value_settings.smooth_decline` `:573`; hardcoded cutoffs: `trade_ideas.py` partner 28/25/24/30 (`:1886`), fit 1.25 delta and 26-30 (`:4150`), `_STANCE_SHEDS_AGING_AGE_FLOOR=28` (`:3943`); `trade_posture._YOUNG_CORE_MAX_AGE=24` (`:554`); `manager_tendencies` young 24 / veteran 32/27/28/28 (`:130-131`); `live_draft` peaks 27/25/26 (`:658`); `waivers_logic` 24/29/31 (`:338-432`); `roster_value_model.YOUNG_COVER_AGE` (`:107`); `team_eval` age-delta 1.25/1.0 (`:234-250`); `drop_candidates` age_cut (`:123`); Sim `aging.py` (separate universe) | The same player is "young", "prime" or "aging" depending on which surface looks. A 27-year-old RB is past prime on the curve (`rankings.py` RB peak 24) but "fine" under most cutoffs. | `rankings.AGE_CURVE_CONTROL_POINTS` + `prime_window_for_position` `:1060`. Add one helper that returns a phase (rising / prime / declining / cliff) and years of prime left per position, and replace all hardcoded cutoffs with it. |
| **Pick value / projected slot** | `trade_ideas._pick_value_components` `:589`, `_pick_team_context` `:316`, `BASE_PICK_VALUES` `:65`; static copy of the base chart `league_rankings.safe_pick_value` `:63`; strategy multiplier `trade_hub_engine.py:175`; `live_draft_trade_evaluator` fallback; Sim `picks.py` + `game_eval.pick_slot_frac` `:481` (separate universe); `playoff_simulator` projects finish but is not used for slots | The base chart is duplicated as a literal (`league_rankings.py:63` says "= trade_ideas.BASE_PICK_VALUES", can drift). Slot projection ignores the schedule/odds simulation we already run. Pick value is lens-dependent (user's posture) for both parties. | `trade_ideas.list_draft_pick_assets` `:861` as the one pricer. Slot source should become playoff-odds expected finish where available (fall back to current blend). Make `safe_pick_value` import the constant. |
| **Positional need / surplus** | `roster_value_model.league_needs` `:1006` (canonical, shared by trade ideas, dashboard, waivers, push, multi-team, glance); `live_draft.roster_position_needs` `:484`; `opponent_profile.room_reads` `:90` + `trade_angle` `:171` (rank-based, drives the League "trade angle"); `team_eval` archetype strengths `:1055`; Sim `game_need.position_report` `:20` (own universe) | The League screen's "trade angle" can say "they have WR depth" while trade ideas (which use `league_needs`) treat that WR room as a need. | `roster_value_model.league_needs`. Rebuild `opponent_profile` on top of it; give `live_draft` the same table. |
| **Trade-history classification** | `team_trade_history` buyer/seller `:59-129`; `manager_tendencies` posture points, shape, picks-in/out `:530-560`, signals `:875` | Two classifiers of the same transactions can label one manager differently on different screens. | `manager_tendencies` (evidence-backed, min samples); `team_trade_history` becomes a thin view of it. |
| **Team strength / draft order** | `team_eval.total_score` rank (used by `_pick_team_context`), `trade_posture.assess` lineup model, `playoff_simulator` | Three notions of "how good is this team" | Lineup-model strength + playoff odds as the primary, `total_score` as fallback. |
| **Injury summaries** | `rankings.summarize_team_injuries` `:3233`, `trade_analyzer_fit.roster_injury_context` `:347`, `injury_status.classify` | Mostly layered, low risk. Keep, but route all through `injury_status`. | `injury_status.classify` |

---

## 4. Proposed handshakes

### 4a. Centrepiece: one `TeamContext` per league

New module `modules/team_context.py` (assembly only, no new math), built once per
(league, lens, rosters signature) and cached the same way `roster_value_model.league_needs`
is (`_rosters_signature` `roster_value_model.py:994`, `derived_cache`). Built beside
`_resolve_trade_posture` (`services/mobile_api_service.py:6452`) and passed into
`trade_hub_engine`, `trade_ideas`, `gm_plan`, `dashboard_engine`, `waivers_logic`,
`push_triggers`, `live_draft`. Every consumer takes `team_context=None` and falls back
to today's behavior (the repo already fails open this way).

```text
TeamContext(league_id, lens, built_at, model_status[])
  teams: { roster_id -> TeamProfile }
  me:    roster_id
  league: { age_mean, age_by_position, pick_slot_model, playoff_odds_ready }

TeamProfile
  posture   { key, group, source: declared|auto|client, confidence, why,
              window }                         <- trade_posture.resolve_posture / assess
  playoff   { odds, title_odds, exp_finish }   <- playoff_simulator.team_odds_row
  age       { avg, league_rank, starter_core_avg,
              by_position: {pos: {avg, phase_mix, prime_years_left}},
              cliff_ids[], rising_ids[] }      <- rankings.age_multiplier / prime_window_for_position
  needs     { needs[], surplus_ids{pos:[id]}, room_coverage }
                                               <- roster_value_model.LeagueNeeds.for_roster
  health    { injured_starter_positions, bye_holes[] }
                                               <- roster_injury_context / bye_cover
  picks     { assets[{season, round, slot, value}], capital, rank, tier,
              firsts, flow{acquired,sent} }    <- trade_ideas pick assets + pick_flow
  tendency  { lean: buyer|seller|none, picks_for_vets, consolidates,
              sample_size, evidence_ids[] }    <- manager_tendencies (min-sample gated; Pro-gated display)
  usage     { rising_ids[], shrinking_ids[] }  <- usage_trends (starters only)
```

Helpers on the context (so consumers do not re-derive): `age_fit(team, assets)`
(uses the curve phase, replaces the hardcoded 28/25 cutoffs), `complement(a, b)`
(needs/surplus overlap, same table both ways), `wants_picks(team)` (posture + age
+ pick capital + tendency), `acceptance_prior(team)` (tendency, bounded and
only after the minimum sample).

Design rules: no new valuation; every field carries `model_status` so a missing
input is reported, never read as "fine"; tendencies are context for ranking and
wording, never a hard filter; keep the Pro gate on anything that exposes
manager-level behavior text.

### 4b. Ranked list

Impact/effort ranking (1 = do first). Effort: S under a day, M 2-4 days, L a week or more.

| # | Handshake | Effort | Impact | Risk | Files touched |
|---|---|---|---|---|---|
| 1 | **Single age-phase helper** from the real curve; replace ~9 hardcoded age cutoffs (trade partner fit, strategy fit, waivers, tendencies, young-core, live draft). Roster/partner ages now mean the same thing everywhere. | S | High | Low (ranking shifts; update tests) | new `modules/age_profile.py` (wraps `rankings.py:141,1060`); `trade_ideas.py:1886,3943,4150`; `trade_posture.py:554`; `waivers_logic.py:338-432`; `manager_tendencies.py:130`; `live_draft.py:658`; `roster_value_model.py:107` |
| 2 | **Partner roster age into trade ideas**: a partner whose core is aging should prefer picks/young; a young partner should not be offered declining vets. Use the already-computed `avg_age` and per-position phase mix (today only in the cache signature, `trade_ideas.py:2802`). | S-M | High (the example the owner gave) | Low | `trade_ideas.py` (`partner_acceptance_context` `:1886`, `_build_team_shape` `:2938`, fit `:4150`), reads #1 |
| 3 | **Partner pick portfolio with projected slots into trade ideas**: ask a partner holding two early 1sts for the pick; offer picks to partners who are short and rebuilding; price a pick at the *partner's* slot and posture, not only the user's lens. | M | High (second example) | Medium (pick value drives acceptance) | `trade_ideas.py` (`_build_roster_pick_assets` `:681`, `_pick_value_components` `:589`, `:4146`, `:4303`), `trade_hub_engine.py:175`, `pick_flow.py` |
| 4 | **Build `TeamContext`** (4a) and migrate Trade Hub first, then GM Plan, dashboard, waivers, push. | L | Very high (unlocks the rest) | Medium (cache keys, memo growth; migrate incrementally behind `team_context=None` fallback) | new `modules/team_context.py`; `services/mobile_api_service.py:6452`; `trade_hub_engine.py`; consumers listed above |
| 5 | **One posture for every team**: apply `refine_team_directions` once upstream of `build_league_rankings_frame` (or drop it), so math, League screens and the dashboard agree; map the 3-state declared stance without losing the 5-state key (declared "Competing" currently collapses to "contender", `team_stance.py:142`). | M | High (fixes visible contradictions) | Medium (labels change on screen; coordinate with product) | `team_eval.py:202,1347`; `league_rankings.py:272`; `mobile_api_service.py:2834,4242`; `dashboard_engine.py:1184`; `trade_hub_engine.py:936` |
| 6 | **Manager tendencies into trade-idea ranking**: bounded acceptance prior and wording ("sold two vets for picks this year") once sample >= minimum; never a hard filter. Unify `team_trade_history` as a view of `manager_tendencies`. | M | High (the largest unused signal) | Medium (Pro gating of manager text; explainability) | `trade_ideas.py` (`partner_acceptance_context`), `manager_tendencies.py`, `team_trade_history.py`, `mobile_api_service.py:5210,5319,6644,7844` |
| 7 | **GM Plan uses the resolved posture and more**: resolved 5-state posture and confidence, roster age profile (cliff players, prime years left), needs/surplus, own pick capital, top waiver add, bye holes, and a "who to call" line from partner tendencies. | M | High (the plan is the narrative surface and is currently thin) | Low-Medium (new copy must stay honest per the module's no-fabrication rule) | `gm_plan.py:336-588`; `mobile_api_service.py:14349-14520` |
| 8 | **Draft room wiring**: feed posture/age profile into the live draft (`_strategy_name` is never populated today), switch `roster_position_needs` to `league_needs`, show rookie ADP value gap and college class strength in the hint, and the partner pick slot in draft-day pick trades. | S-M | Medium-High (draft is a high-attention moment) | Low | `live_draft.py:484,643,652,658`; `draft_assistant.py`; `mobile_api_service.py:5065,5101`; `live_draft_trade_evaluator.py` |
| 9 | **Playoff odds as the slot and posture engine**: derive projected pick slot and "buyer/seller" from `simulate_playoff_odds` expected finish (fall back to the current blend). | M | Medium-High (better slots, better posture for every team) | Medium (sim cost, cache bucket; offseason falls back) | `trade_ideas.py:316`; `trade_posture.py:175`; `playoff_simulator.py:661`; `record_signal.py` |
| 10 | **Usage/role trends into target selection** for trade ideas and GM Plan (rising role = buy, shrinking role = sell), currently only in waivers, analyzer notes and multi-team guard. | M | Medium | Low-Medium (data freshness; `usage_trends_unavailable` status already exists) | `trade_ideas.py` (target scoring, hub overflow `:4658`), `usage_trends.py`, `gm_plan.py` |
| 11 | **Waivers read the context**: age phase instead of hardcoded cutoffs, pick capital/posture for "stash vs win-now", competing needs from other teams (contested add, FAAB urgency). | M | Medium | Low | `waivers_logic.py`, `faab.py`, `mobile_api_service.py:17573-17990` |
| 12 | **Rebuild the League "trade angle" on the shared need table** (kills the rank-based second engine) and cross-link it to Trade Hub ideas. | S-M | Medium (consistency) | Low | `opponent_profile.py:90,171`; `mobile_api_service.py:3168-3245`, `:2851-3000` |
| 13 | **Outcome and decision-memory feedback**: use `trade_outcome_results` and verdict feedback to calibrate idea ranking (which idea shapes the user actually completed and kept) and to avoid re-suggesting rejected ideas. | L | Medium (long-term compounding) | High (small samples, feedback loops; needs a design doc and an opt-in) | `trade_outcome_results.py`, `decision_log.py`, `verdict_feedback`, `trade_ideas.py` |
| 14 | **Notifications from context**: trigger trade pushes only when a partner is a real fit (age + pick + need) and phrase from the context; add bye-hole and aging-cliff alerts. | S-M | Medium | Low | `push_triggers.py:756,1034,1134`; `notification_decider.py` |
| 15 | **Shared pick constant**: make `league_rankings.safe_pick_value` import `trade_ideas.BASE_PICK_VALUES`. | S | Low (prevents drift) | Very low | `league_rankings.py:63`; `trade_ideas.py:65` |
| 16 | **External interesting-trades**: tag with the real owners' postures to rank "interesting" (valuation stays neutral). | S | Low | Low | `external_interesting_trades.py:55,150,253` |

### 4c. Sim AI GMs

The Sim is its own universe (synthetic players, own aging/pick/need models), so
`TeamContext` is not shared with it. The same ideas apply internally, but
**every Sim change needs a new versioned flag** so old saves replay byte for byte
(`modules/sim/game_rules.py`: add the `*_VERSION` constant in `game_types.py`
next to `POSTURE_VERSION` `:61`, register it in `UPGRADABLE_FLAGS` with a
boundary, add its `FLAGS` copy, keep the default 0 for existing saves, and add a
replay-identity test). Candidates, all new flags:

| Candidate flag | Change | Boundary | Effort |
|---|---|---|---|
| `roster_age_v` | AI horizon shift also reads its own roster's age vs the league (an old roster that is losing sells; a young winning roster holds), on top of `game_posture.apply_posture` `:106` | week | S-M |
| `partner_v` | AI trade proposals consider the counterparty's needs and pick portfolio (AI-to-AI and counters to the user), reusing `game_need.position_report` and `game_eval.pick_slot_frac` | now | M |
| `memory_v` | AI remembers recent trades with the user (event-sourced, bounded) and adjusts acceptance/ask, mirroring the real-league tendencies idea | now | M |
| `pickneed_v` | AI values picks by its own pick capital and next-draft slot need (rebuilders hoard, thin-drafted teams buy) | now | S |

Do not edit `aging.py` knots, `game_posture.py` thresholds, or
`personas.py` constants in place for any of these: that would change old saves.

### 4d. Suggested sequence

1. Small, safe first: #1 age-phase helper, #15, then #2 partner age (S-M).
2. Fix visible contradictions: #5 one posture, #8 draft-room wiring, #12.
3. Centrepiece: #4 `TeamContext`, migrating Trade Hub, then #3 and #6 on top of it.
4. Narrative surfaces: #7 GM Plan, #11 waivers, #14 notifications, #10 usage.
5. Long-term: #9 odds-driven slots, #13 outcome feedback (design doc first), Sim flags.

### 4e. What already works (do not redo)

- One need/surplus table shared by trade ideas, dashboard, waivers, push, multi-team and glance (`roster_value_model.league_needs`).
- One resolved posture for the user's own team with declared > auto > client and a confidence (`trade_posture.resolve_posture`).
- Multi-team trades grade each participant under its own posture and age curve.
- Partner posture, needs and incoming-age fit already shape partner acceptability (`partner_acceptance_context`, with #2116/#2117).
- Record-aware slot projection and posture (`record_signal.blend_percentile_with_record`).
