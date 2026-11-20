# Roster % snapshots (2026-11)

Daily history for the Players hub Trending mode (trend = 7-day change in roster %).

- Source: ESPN public ownership via `modules/public_roster_percentages.py`. Sleeper trending adds (`sleeper_trending_add*`) were NOT persisted anywhere before; they are now stored as `sleeper_trending_adds` (null when the player is not on Sleeper's top-200 list or the call failed).
- Store: Supabase `public.roster_pct_snapshots`, one row per (player_id, source, snapshot_date), upserted so same-day reruns are idempotent. Rows older than 400 days are pruned by the same job.
- Needs from coridian_: run `docs/supabase_roster_pct_snapshots.sql` once in the Supabase SQL editor (additive).
- Job: `.github/workflows/roster-pct-snapshot.yml` (daily 07:20 UTC, plus `workflow_dispatch`). GitHub schedules can run late; for on-time runs use this root-crontab line on the box (pattern from `2026-11-data-truth.md` section 11; the container already holds the Supabase secrets):

```
20 7 * * * flock -n /var/lock/fgl-roster-pct.lock sh -c 'C=$(docker ps -qf name=mobile-api | head -n1); [ -n "$C" ] && docker exec "$C" python scripts/run_roster_pct_snapshot.py || echo "no mobile-api container"' >> /var/log/fgl/roster-pct-snapshot.log 2>&1
```

  No percent sign appears in the line; if one is ever added it must be written as backslash-percent. Duplicate runs are harmless.
- Read: `modules.roster_pct_history.get_roster_pct_trend(player_ids, days=7)` returns `{current, previous, delta, current_date, previous_date}` per player, or `None` when there is no current snapshot (today or yesterday) or no baseline within one day of the target date. Nothing is interpolated.
