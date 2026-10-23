# News-driven value events (2026-10)

Closes the top finding of `docs/logic-audit-2026-10-r2.md` ("no news-to-value link beyond
Sleeper injury status") **conservatively**. Shipped behind `DYNASTYGM_NEWS_VALUE_EVENTS`
(default `0`): merging changes nothing in production.

## What it does

`modules/news_value_events.py`. Only structured feed transitions, never headline text:

| Type | Source | State |
| --- | --- | --- |
| `availability_out` (Sleeper Out / IR / PUP / Suspended; subtype kept for provenance) | `status` / `injury_status` transitions seen by `scripts/sync_injury_status.py` | **enabled** (evidence below) |
| `team_change` (trade / signing / release) | per-week team code | **disabled**: 16 usable events in 5 seasons, no detectable effect |
| `depth_chart_role` | `data/depth_chart_snapshots.json` | **disabled**: one weekly snapshot, no history to validate |

Not used: transactions. Sleeper `transactions` are fantasy-league moves, not NFL trades; there is no
NFL transaction feed in the repo.

Behaviour of an enabled type:

- **Cap**: `max_reduction` = 0.19 (-19%). Derived as 0.28 (share of the composite that is
  current-season-sensitive: production .12 + opportunity .10 + role .06) x 0.69 (measured first-game
  shortfall below). Market/age terms are long-horizon and are not touched by a short availability shock.
- **Decay**: exponential, half-life 28 days (measured shortfall by game after the event: .69, .53,
  .41, .41).
- **Expiry**: hard stop at 28 days (the backtest measured four games; never extrapolated), and the
  event is cleared the moment the feed stops carrying an availability status (store clears it on the
  transition; the valuation also ignores it if the live row no longer shows one).
- **No double count**: the adjustment is `min(1, (1 - reduction) / injury_multiplier)`, i.e. only the
  part beyond what `rankings.injury_multiplier` already discounts (Out 0.80, IR/PUP/Sus 0.68).
- **One place**: `rankings.compose_composite_score` (used by the full model, the injury refresh and the
  hydrate path), so rankings, Trade Hub, Analyzer and Waivers read the same score.
- **Provenance**: columns `news_event_type`, `news_event_provenance` (JSON: event type, subtype, source,
  detected_at, from/to status, raw reduction, existing injury multiplier, applied adjustment, expiry) and
  `news_factor` = signed applied adjustment (previously hard-coded 0.0). Columns exist only when the flag is on.
- **Store**: `data/news_value_events.json` (gitignored; override `DYNASTYGM_NEWS_VALUE_EVENTS_PATH`).
  Written by the injury-sync cron on status transitions. **Deployment caveat:** the cron host and the web
  API must share this file (or it must move to Supabase) before turning the flag on; otherwise the API
  sees no events and the layer is a no-op.
- Limitation: only transitions observed while the flag is on open an event; players already Out/IR at
  switch-on get none (the static injury multiplier still covers them).

## Backtest

`scripts/news_value_events_backtest.py` (`fetch`, `run`). Sleeper keeps no point-in-time injury history,
so events are reconstructed from Sleeper weekly stats, which carry the player's team that week and games
played, 2021-2025 (throwaway cache, nothing committed):

- `availability_out` proxy: established player (>=4 prior games, trailing-8 PPG >= 6, played his previous
  team game) has no game in a week his team played (byes excluded). **The proxy cannot separate injury
  from suspension or healthy scratch**, which is why one cap serves the whole type.
- `team_change`: team code differs from his previous game's team and he played.
- Target: PPR points over the next four team games, starting the game *after* the missed one (so the
  known-out week does not trivially favour the adjustment). Baseline = trailing PPG x 4 (a value that has
  not heard the news). Rank correlation is over event rows plus same-week control rows (players who played
  and kept their team), so a subset multiplier can change the ranking.
- Walk-forward: the adjustment ratio is fitted only on earlier seasons. Arms: raw baseline, the
  production static multiplier (Out = 0.80), and the fitted event ratio.

`availability_out`, n = events (controls ~1,630 per season):

| Test season | n | fitted ratio | MAE raw | MAE static 0.80 | MAE event-fit | MAE gain vs static, 95% CI | Spearman raw / static / event |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 2023 | 79 | 0.423 | 31.36 | 25.40 | 18.99 | +2.9 to +9.8 | .498 / .516 / .530 |
| 2024 | 102 | 0.427 | 30.67 | 24.34 | 17.43 | +3.8 to +9.9 | .503 / .527 / .549 |
| 2025 | 102 | 0.421 | 31.35 | 24.62 | 17.74 | +3.9 to +9.9 | .508 / .532 / .554 |

Realised / expected points by game after the event (all seasons, expected = trailing PPG): control
.90 / .87 / .84 / .80; `availability_out` .28 / .41 / .50 / .47 (n = 533; 33% score zero in all four).
By position the ratio is 0.34 K, 0.35 QB, 0.42 TE, 0.43 RB, 0.46 WR. Control rows are also below 1.0
(selection on high trailing PPG plus ordinary missed games), so the fitted ratio overstates the news
effect; the caps use the shortfall *relative to control* (`1 - .28/.90 = .69`).

`team_change`: n = 1, 3, 3 in 2023 / 2024 / 2025 (16 in five seasons). Fitted ratio ~0.9, MAE gain CI
spans zero (-2.0 to +3.2, -3.3 to +4.1). **Not enabled.**

### Honest reading

- Next-4-game output is predicted clearly better with the availability event than with the status quo,
  in all three held-out seasons (CIs exclude zero), and rank correlation improves by ~.02-.05.
- But the value consequence is small. At pass-through 0.28 the day-0 cap (-19%) is about the same as
  what the static multiplier already does for Out (-20% on 78% of the composite ~ -16%) and less than IR
  (-25%). So when the feed already shows the status, the incremental adjustment is **zero** by design.
  The layer's practical effect today is provenance, decay/expiry evidence, and a single audited place
  to extend, not a visible value change. That is the conservative outcome the task asked for; it is not
  a large value win.
- The proxy mixes causes and the 0.28 pass-through is a judgment call, not fitted: dynasty value has no
  ground-truth target in this repo.

## Recommendation

1. Merge as-is (flag off, no change).
2. If turned on, enable `availability_out` only (already the only enabled type). Expect near-zero
   visible value change; its job is explanation and a safety net for statuses the multiplier misses.
3. Keep `team_change` and `depth_chart_role` off until there is point-in-time history (log team and
   depth-chart snapshots weekly from now; re-run the backtest after a season).
4. Before enabling in production, decide where the event store lives (shared with the API).
