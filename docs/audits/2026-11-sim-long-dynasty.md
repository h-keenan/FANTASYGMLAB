# Sim dynasty up to 20 seasons (2026-11)

Ask (coridian_): "we definitely need more than five years on the fantasy sim... 20 is probably the max I would even go."
New games can run 3, 4, 5 (default, unchanged), 10, 15 or 20 seasons (`GameSettings.seasons` is saved with the game; old saves keep
the length they were created with). Everything that changes engine behavior is gated on `dynasty_v >= 3` (new dynasties only).

## What broke past season 5 (measured with the old engine, dynasty_v 2, forced to 20 seasons)

| 3 seeds, mean | s1 | s5 | s10 | s15 | s20 |
| --- | --- | --- | --- | --- | --- |
| team lineup score / p99 | 101.7 / 159 | 86 / 142 | 67 / 128 | 53 / 106 | 45 / 90 |
| top-12 RB / WR / TE ppg | 18.4 / 17.1 / 11.7 | 15.0 / 16.4 / 9.7 | 9.3 / 15.1 / 6.8 | 5.6 / 11.9 / 3.8 | 3.5 / 11.5 / 2.8 |
| kickers in the pool | 30 | 25.7 | 18.3 | 8 | 0.3 |
| QBs in the pool | 33 | 35 | 35.7 | 28.7 | 26 |

Root causes: (1) rookie classes were scaled to the 12th-best veteran of the CURRENT, already-aged pool, so weaker veterans made weaker
classes which made weaker veterans (a deflation spiral); (2) kickers are never drafted, so as they retire the position empties; quarterbacks thin
the same way (few class slots, late and weak); (3) kickers' age curve compounds +2% a year, and nothing bounds the top of the pool.
Cost was not the problem: a 20-season game takes 65-110 s wall in total on one core (3-5 s per season including the offseason).

## What dynasty_v 3 changes (`game_dynasty.py`, `aging.py`)

- **League anchor**: classes are scaled to the league's own season-1 level (rank-12 mean and market by position), a fixed yardstick.
- **Refill to equilibrium** (`_equilibrium_plan`): each year's class fills the head-count holes retirements and aging leave at QB/RB/WR/TE and
  K (kickers go last and are drawn from the league's own kickers), plus the usual class size spread by the position shares, leaning toward thin
  positions. Quarterbacks are early (first one, 67%) or inside the first 24 slots, never throw-ins.
- **Supply response** (`_supply_response`): a position whose veteran depth (top-N average) slips below the season-1 level draws a stronger class
  (and a weaker one when it runs ahead), `(league level / current level)^1.6`, bounded to [0.85, 1.5]. Draft classes chase scarcity.
- **Top bound**: nobody runs far past the league's best (compression above 1.1 x the season-1 best at the position); kickers keep their level
  until their late decline.
- **Bounded state**: rookie drafts older than 4 seasons shrink to the user's own picks and their spent-pick ledger rows are dropped (the ledger
  invariant still holds); season pools kept in memory behind the latest 2 (older ones rebuild on demand, 0.8-0.9 s cold for season 20).
- **History**: the dynasty summary carries `history` (champions, title leaders, best record, most points) and drops the per-year standings table.
- Cap: `MAX_SEASONS = 20`, choices (3, 4, 5, 10, 15, 20), default 5.

## Equilibrium after the change (3 seeds x 20 seasons, player-model-4, AI ai_v 1, 12 teams, pool from the real 2025 panel)

| mean | s1 | s5 | s10 | s15 | s20 |
| --- | --- | --- | --- | --- | --- |
| team lineup score / p99 | 101.7 / 159 | 94.9 / 158 | 90.4 / 151 | 94.9 / 164 | 93.2 / 176 |
| top-12 QB / RB / WR / TE ppg | 22.3 / 18.4 / 17.1 / 11.7 | 23.7 / 19.3 / 17.7 / 11.6 | 23.2 / 18.5 / 18.7 / 11.7 | 22.9 / 19.7 / 19.0 / 11.9 | 24.2 / 19.4 / 18.8 / 11.4 |
| rank-24 RB / WR / TE ppg | 12.7 / 13.7 / 7.3 | 11.4 / 12.9 / 6.0 | 11.1 / 11.9 / 6.0 | 10.3 / 12.2 / 5.9 | 11.7 / 12.0 / 5.7 |
| pool size / kickers / QBs | 383 / 30 / 33 | 453 / 30 / 38 | 482 / 30 / 41 | 474 / 30 / 37 | 459 / 30 / 38 |
| starter age mean | 27.2 | 26.8 | 26.9 | 26.3 | 26.7 |
| top-5 rookie ppg | n/a | 17.4 | 17.3 | 22.3 | 17.1 |
| weekly scores over 40 | 0.34% | 0.31% | 0.19% | 0.27% | 0.38% |

Reading: after the first drop (the season-1 pool is the freshly drafted best of the league) the league plateaus about 8% below season 1 and stays there
(s10 90, s15 95, s20 93); the top of every position holds; the mid-depth is 5-20% below season 1 (QB ranks 13-36 are thinner: 8.4 vs 15.3 at rank 25-36,
a known soft spot); the pool grows 20% and flattens (undrafted rookies join the free-agent pool); starters' ages stay 26-27 (oldest starter 36-41, kickers);
no kicker or QB shortage; player-model-4 tails hold (max weekly score 58-69, over-40 share under 0.4%). Not tuned further: the plateau is the
honest level of a league whose talent is replaced every year.

AI managers (ai_v 1) over 20 years: roster size 14.3-15.9, kickers 1.0-1.5, QBs 1.4-2.7, WR 4.6-6.5; about 60-100 waiver adds and 8-14 AI trades per
league-season, flat across the years, no hoarding.

## Cost at 20 seasons (one game, one core; `python -m modules.sim.calibration.dynasty_report --seeds 3 --seasons 20`)

| | s1 | s5 | s10 | s20 |
| --- | --- | --- | --- | --- |
| Home / League / Players payload | 19 / 27 / 16 KB | 22 / 27 / 16 KB | 22 / 27 / 16 KB | 19 / 27 / 16 KB |
| dynasty summary payload (history) | 1.4 KB | 5.1 KB | 8.6 KB (s9) | 18 KB |
| saved state (checkpoint) | 48 KB | 89 KB | 102 KB (s9) | 139 KB (was 233 KB) |
| events in the log / cold replay of all of them | 734 / 0.01 s | 2,979 / 0.03 s | 5,289 / 0.06 s | 11,356 / 0.12 s |
| view build (home / league / players) | 28-35 / 13 / 28 ms | 28 / 14 / 28 ms | 30 / 15 / 22 ms | 27 / 16 / 22 ms |

Payloads and latencies are flat in the season count. The event log grows about 0.5 MB per season (the weekly recap), which only matters
for storage; reads use the latest checkpoint plus the events after it.

## Versioning and tests

`dynasty_v` 3 is stored in settings; v2 dynasty games replay exactly as before (3- and 4-season goldens taken on origin/main are pinned in
`tests/test_sim_dynasty_long.py`). The same file covers the cap and choices, the equilibrium plan, a 12-season equilibrium run (kickers/QBs held,
top-12 and scoring within bands, tails, bounded state), compaction ledger invariants, resume == replay on a compacting game, view eviction, and
the summary history. Client: League history (champions list, title leaders, records) in the dynasty result card on web and mobile; the length
picker comes from the server's options, so Advanced options show 3, 4, 5, 10, 15, 20 with 5 as the default; "N of 20 seasons played" copy was
already generic.
