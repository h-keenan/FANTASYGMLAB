# Trade Hub CPU, allocation, and execution-flow investigation

## Verdict

No production Trade Hub behavior was changed. The investigation recommends
exactly one next optimization: compute `_pick_team_context()` once per roster
inside one raw-board generation invocation and pass/reuse that immutable context
while constructing draft-pick assets.

On the primary controlled 12-team Superflex fixture, the current implementation
calls `_pick_team_context()` 96 times: 12 rosters x two seasons x four rounds.
Only 12 input combinations are distinct because the helper depends on roster ID
and the same league-summary frame, not season or round. A measurement-only local
reuse experiment preserved the complete golden board exactly and changed median
calculation time from 1164.01 ms to 927.64 ms, a 236.37 ms or 20.31% reduction.

## Environment and fixture safety

- Windows local process, Python repository virtual environment
- fixed validation date: 2026-07-30
- current base: `340a12d974367854564db141d1c923b829ac903a`
- synthetic deterministic player IDs such as `F01-00`
- synthetic team labels only
- no customer accounts, usernames, league IDs, roster IDs, tokens, or traffic
- current production formulas and Trust code
- raw generation executed through `_build_trade_ideas_impl()` with the normal
  `_TradePipelineProfile`
- post-cache enforcement executed through `enforce_trade_board()`
- presentation preparation executed through `group_trade_hub_ideas()` and
  `trade_card_presentation_contract()`

Fixtures:

| Fixture | Teams | Roster | Players | Format | Other context |
| --- | ---: | ---: | ---: | --- | --- |
| 8-team 1QB shallow | 8 | 22 | 176 | 1QB | contender |
| 8-team Superflex | 8 | 26 | 208 | Superflex | contender |
| 12-team 1QB deep | 12 | 28 | 336 | 1QB | TE premium, rebuild |
| 12-team Superflex primary | 12 | 28 | 336 | Superflex | TE premium, contender |
| 14-team Superflex deep | 14 | 30 | 420 | Superflex | TE premium, retool |

The 12-team Superflex fixture used 20 samples. Other fixtures used 10. Small
sample p95 values are directional and are not production SLOs.

## Production call graph

```text
app.py route == trade_hub
  -> get_shared_league_context() [5-minute league-context caches]
  -> get_team_vs_league(selected roster)
  -> strategy selector and apply_strategy_age_curve()
  -> cached_trade_ideas() [st.cache_data, TTL 5 minutes]
     -> build_trade_ideas()
        -> _build_trade_ideas_impl()
           -> copy/normalize player frame [league-wide]
           -> adapter.get_rosters() [league-wide]
           -> ownership map [league-wide]
           -> _build_roster_pick_assets()
              -> each roster x season x round
              -> _pick_value_components()
              -> _pick_team_context() [repeated roster-wide input]
           -> build roster team frames [roster-wide]
           -> protected outgoing filter [selected team]
           -> get_team_vs_league(selected team)
           -> _build_team_shape(selected team)
              -> get_team_vs_league
              -> suggest_optimal_lineup
              -> summarize_team_injuries
              -> true_roster_needs/classify_roster_rooms
           -> for each partner
              -> _build_team_shape(partner) [once per partner]
              -> candidate/player/pick construction
              -> outgoing x incoming package loops
              -> fit, strategy, injury, market-realism, fairness scoring
              -> confidence fields
              -> package-key duplicate suppression
           -> final sort and diversity selection
     [cache stores raw recommendations]
  -> enforce_cached_trade_ideas() [outside cache]
     -> canonical candidate-player lookup
     -> roster ownership/valid-roster context
     -> enforce_trade_board()
     -> record_trust_diagnostics()
  -> manager-tendency enrichment
  -> primary/secondary split
  -> headline selection
  -> group_trade_hub_ideas()
  -> trade_card_presentation_contract()
  -> Streamlit card and action rendering
```

### Scope and call-frequency classification

| Function/stage | Primary calls | Parent | Scope | Repeated equivalent input? |
| --- | ---: | --- | --- | --- |
| `_build_trade_ideas_impl` | 1 | cached raw generator | league | no |
| `_build_roster_pick_assets` | 1 | raw generator | league | no |
| `_pick_team_context` | 96 | pick valuation | roster | yes: 8 calls per roster |
| `_build_team_shape` | 12 | raw generator | roster | no within generator |
| `get_team_vs_league` | 13 | selected metrics + shapes | roster | selected roster called twice |
| `suggest_optimal_lineup` | 12 | team shape | roster | no within generator |
| `true_roster_needs` | 12 | team shape | roster | no within generator |
| `summarize_team_injuries` | 12 | team shape | roster | no within generator |
| `_row_score` | 674 | asset construction | player | different rows/candidates |
| `_score_assets` | 5,396 actual builds | package scoring | package | memoized |
| package-score requests | 15,834 | candidate loops | candidate | 10,234 cache hits |
| package construction | 16,448 | candidate loops | candidate | partially overlapping |
| candidate target generation | 11 | partner loop | partner | distinct partner |
| confidence scoring | 10 | accepted candidates | candidate | distinct |
| final sorting | 1 | raw generator | board | no |
| Trust recommendation validation | 10 | post-cache boundary | recommendation | distinct |

## Timing matrix

“Cold” below means a raw-recommendation generation miss with Trust and
presentation preparation. It is not an infrastructure/process cold start.
“Warm” reuses the exact raw recommendation list and still performs Trust and
presentation preparation.

| Fixture | Cold median | Directional p95 | Warm raw-hit median | Raw / approved / displayed |
| --- | ---: | ---: | ---: | --- |
| 8-team 1QB shallow | 732.01 ms | 746.77 ms | 5.47 ms | 16 / 16 / 16 |
| 8-team Superflex | 796.02 ms | 823.16 ms | 6.75 ms | 20 / 20 / 20 |
| 12-team 1QB deep | 1080.75 ms | 1107.64 ms | 6.31 ms | 20 / 20 / 20 |
| 12-team Superflex primary | 1169.89 ms | 1199.55 ms | 5.51 ms | 10 / 10 / 10 |
| 14-team Superflex deep | 1265.66 ms | 1293.93 ms | 6.79 ms | 20 / 20 / 20 |

The Streamlit cache-hit measurement does not include Streamlit’s DataFrame
hashing/deserialization overhead; it isolates the work that remains after raw
retrieval. Normal rendering and websocket/browser time were not measured here.

## Primary candidate funnel

- player pool: 336 players
- trade partners: 11
- package constructions: 16,448
- package-score requests: 15,834
- actual `_score_assets` calculations: 5,396
- package-score cache hits: 10,234
- accepted before duplicate suppression: 10
- duplicate accepted packages: 0
- raw recommendations: 10
- Trust validations: 10
- Trust approved: 10
- displayed card models: 10

Candidate counts were not reduced. Existing memoization already avoids 64.6%
of package-score recalculations in this fixture.

## CPU profile

cProfile overhead raises absolute duration; the timing matrix is the wall-clock
decision evidence.

| Rank | Function | Calls | Cumulative | Classification |
| ---: | --- | ---: | ---: | --- |
| 1 | `_build_trade_ideas_impl` | 1 | 2861.29 ms | required orchestration |
| 2 | `_build_team_shape` | 12 | 1121.18 ms | required roster preparation |
| 3 | pipeline `cached()` | 7,590 | 736.99 ms | required/memoized |
| 4 | `make_reasoned_idea` | 1,231 | 601.33 ms | candidate evaluation |
| 5 | `_build_roster_pick_assets` | 1 | 587.39 ms | repeated preparation |
| 6 | `_pick_value_components` | 96 | 584.94 ms | pick valuation |
| 7 | `_pick_team_context` | 96 | 568.42 ms | avoidable repeated preparation |
| 8 | DataFrame `__getitem__` | 1,424 | 452.51 ms | conversion/filtering |
| 9 | `summarize_team_injuries` | 12 | 407.69 ms | required roster context |
| 10 | `true_roster_needs` | 12 | 370.23 ms | required roster context |
| 11 | `classify_roster_rooms` | 12 | 369.78 ms | required domain calculation |
| 12 | `_trade_reasoning_context` | 1,231 | 351.42 ms | candidate scoring |
| 13 | DataFrame `take` | 551 | 307.94 ms | allocation/filtering |
| 14 | manager `take` | 550 | 293.52 ms | allocation/filtering |
| 15 | boolean DataFrame filtering | 241 | 270.30 ms | player/candidate filtering |
| 16 | manager reindex | 562 | 259.68 ms | allocation/filtering |
| 17 | market-realism evaluation | 1,231 | 205.25 ms | required scoring |
| 18 | `injury_level` | 12,083 | 203.34 ms | repeated candidate context |
| 19 | DataFrame apply | 75 | 199.67 ms | conversion/preparation |

The remaining top-25 entries are pandas block operations and lambdas inside the
same candidate reasoning/market paths. Trust and presentation preparation are
not material on the 10-result raw-cache-hit path (combined median 5.51 ms).

## Allocation and DataFrame audit

Primary run:

- DataFrame `copy()` observations: 472, including pandas-internal copies
- explicit DataFrame merges: 0
- `sort_values()` observations: 12
- traced peak: 4,416,904 bytes
- retained: 105,816 bytes in 1,620 blocks

Largest direct copy sites:

| Site | Calls | Maximum shape | Maximum shallow/deep estimate |
| --- | ---: | --- | ---: |
| `trade_ideas.py:2570` initial player copy | 1 | 336 x 32 | 179,292 bytes |
| `trade_ideas.py:2601-2602` assign/drop/group preparation | 2 | 336 x 33 | 181,980 bytes |
| `trade_ideas.py:2600` roster frames | 12 | 28 x 33 | 15,296 bytes each |
| `team_eval.py:262/265` lineup preparation | 24 | 28 x 32/33 | 15,296 bytes each |
| `rankings.py:1089/1123` injury preparation | 24 | 28 x 32 | 15,072 bytes each |
| `roster_needs.py:194` room classification | 12 | 28 x 32 | 15,072 bytes each |

Five possible allocation reductions, not implemented:

1. avoid repeated full-summary copies inside `_pick_team_context`;
2. reduce intermediate boolean-filter DataFrames in candidate reasoning;
3. reuse proven-equivalent lineup/room inputs inside one roster-shape build;
4. avoid copying the complete player frame if ID normalization can be isolated;
5. reduce repeated candidate asset-list construction.

Only item 1 currently has exact input proof and a measured low-risk experiment.

## Duplicate-work proof

### Proven identical

`_pick_team_context(original_roster_id, df_summary)` receives the same
`df_summary` object and the same roster ID eight times per roster. Season and
round are not inputs. Each call:

- copies the league summary;
- converts roster IDs and scores;
- drops invalid rows;
- ranks the same scores;
- selects the same roster;
- returns the same tier, modifier, and percentile.

There are 96 calls but 12 distinct results in the primary fixture. The
measurement-only reuse experiment returns the original object for each roster
only inside one invocation and produced byte-identical golden output.

### Partially overlapping but not proven removable

- team-shape calculations execute once per roster and have different team
  frames, metrics, lineups, injury states, and needs;
- 1,231 reasoning and market checks use different packages, although existing
  package-key memoization catches repeat keys;
- candidate asset scoring repeats asset values across different package keys,
  but the existing score cache already records 10,234 hits;
- `injury_level` sees repeated assets across candidates, but changing that
  boundary could affect malformed/null behavior;
- app-level shared roster profiles overlap conceptually with trade shapes but
  do not expose an identical contract, so reuse is not yet proven.

The selected-team `get_team_vs_league()` call is trivially repeated once by
`_build_team_shape()`, but its measured opportunity is far below the chosen
candidate.

## Complexity and observed scaling

Major practical loops:

- roster/pick preparation: teams x two seasons x four rounds;
- roster shapes: teams, each scanning its roster and constructing a lineup;
- partners: teams minus one;
- candidate packages: each partner’s top incoming assets crossed with up to
  10-12 outgoing assets, plus optional pick combinations;
- scoring: candidate packages x fit/reasoning/market stages;
- Trust: final raw recommendations only.

Observed cold medians:

- 8-team Superflex, 208 players: 796.02 ms;
- 12-team Superflex, 336 players: 1169.89 ms (+47.0%);
- 14-team Superflex, 420 players: 1265.66 ms (+59.0% versus 8-team).

Shape/lineup/needs/injury calls grow 8 -> 12 -> 14. Pick-context calls grow
64 -> 96 -> 112. Partner target-generation calls grow 7 -> 11 -> 13.
Package counts depend on strategy, accepted paths, roster depth, and pick
availability, so they are not purely linear.

## Cache-boundary audit

### `cached_trade_ideas`

- `st.cache_data`, TTL five minutes
- keys include the player DataFrame, league ID, summary DataFrame, selected
  roster, untouchables, role map, score field, pick multiplier, strategy,
  archetype, normalized league settings, draft status, and max ideas
- returns raw `list[dict]`
- DataFrame hashing may be material but was not isolated by this harness
- mutation isolation is provided by Streamlit’s serialized cache return
- Trust is intentionally outside and runs after every retrieval

### `cached_player_trade_hub_ideas`

- `st.cache_data`, TTL five minutes
- adds mode and selected player ID to the team-board key dimensions
- returns a raw search-result dictionary
- Trust remains outside

### league-context caches

- core summary/intelligence/context functions use five-minute TTLs
- include league, player frame, and league-setting inputs
- provide league/UI context but do not cache final enforced trade boards

No user-specific Trust decision enters a shared public cache. No enforced
recommendation is cached. The current boundary is correct. Possible low hit
causes are full DataFrame hashing and strategy/role/untouchable changes, but
those inputs are semantically necessary.

## Golden equivalence baseline

`tests/fixtures/trade_hub_golden.json` stores only synthetic fixture IDs and:

- ordered trade sides;
- scores, values, gains, confidence, market labels, and fit grades;
- Trust disposition and diagnostics;
- displayed group;
- raw, approved, and displayed counts.

It covers five league/strategy/depth fixtures plus zero-approved,
one-recommendation, and empty-board edge cases. Tests separately cover malformed
cached candidates, a Trust-blocked candidate, cached/uncached equality,
duplicate-value-safe stable ordering through full golden equality, missing
identity, and failure propagation.

## Top five next optimization candidates

1. **Reuse `_pick_team_context` once per roster per generation.** Proven
   identical, 232.52 ms measured median reduction, isolated, no formula change.
2. Reuse or streamline team-shape subcontexts. Potentially large (1121 ms
   cumulative), but inputs differ per roster and existing shared context is not
   contract-equivalent.
3. Reduce repeated injury classification across candidate packages. About
   203 ms profiled, but null/malformed and package-specific semantics raise risk.
4. Reduce DataFrame filtering/copying in candidate loops. Many calls and a
   4.4 MB peak, but no single safe boundary yet explains 150 ms.
5. Further package/asset-score reuse. High call volume, but current memoization
   already eliminates 10,234 of 15,834 requests, limiting additional ROI.

## Exactly one recommended implementation

Add a local immutable `team_pick_context_by_roster` mapping inside
`_build_roster_pick_assets()` and pass the relevant precomputed context into
`_pick_value_components()` through an additive internal-only argument.

Expected behavior:

- compute `_pick_team_context` 12 rather than 96 times in a 12-team league;
- keep season, round, projection, format, class, and prospect formulas unchanged;
- keep cache keys and raw recommendation output unchanged;
- keep Trust entirely outside raw generation;
- retain no state after the build returns.

Expected gain from the controlled primary fixture:

- 1164.01 ms -> 927.64 ms median;
- 236.37 ms absolute;
- 20.31% reduction;
- stronger absolute savings as team count grows.

Expected files:

- `modules/trade_ideas.py`;
- a focused differential/performance regression test;
- no `app.py` changes.

Risk is low but not zero: accidental mutation of the context dictionary or
different fallback behavior for malformed summary rows. The implementation
should use an immutable/read-only value or copy at the existing consumer
boundary and compare all five golden fixtures exactly. Rollback is one focused
commit reverting the local context map.

## Measurement gaps

- no real Streamlit websocket/browser rendering;
- no production infrastructure, network, or Sleeper latency;
- no Streamlit DataFrame-hash/deserialization timing;
- card HTML construction and browser paint were not measured;
- synthetic fixtures are realistic in size and shape but not evidence of
  production p95 behavior;
- manager-tendency enrichment was mapped statically but excluded from the
  calculation harness because it depends on separate league-maturity evidence;
- no customer or organic production data was used.

These gaps do not affect the selected duplicate-work proof because the pick
context inputs and output equality are entirely inside raw generation.
