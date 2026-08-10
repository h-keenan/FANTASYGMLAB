# Tail Latency / 15-Second Load Diagnosis (#230)

| Field | Value |
| --- | --- |
| Baseline | `869687fb9e590a107f52b16b7506d97441ef5aad` (#229) |
| Scope | Instrumentation + causal diagnosis + correctness-safe duplicate/post-READY detection |
| Gate | Detailed rows / summary behind `DYNASTYGM_STARTUP=1` |

## User-perceived milestones (do not collapse)

| Code | Milestone keys |
| --- | --- |
| A App shell visible | `shell_chrome_ready`, `workspace_chrome_ready` |
| B Loading dismissed | `loading_dismissed` |
| C First useful | `first_usable_paint`, `game_plan_first_useful` |
| D Game Plan ready | `game_plan_composed`, `game_plan_package_ready` |
| E Dashboard complete | `dashboard_football_ready`, `dashboard_rendered` |
| F Interactive stable | summary trigger once dashboard complete |

## Correlated startup trace

Enriched `startup_milestone` / `startup_stage_duration` / `startup_trace_summary` rows can carry:

`startup_session_id`, `startup_run_number`, `run_cause`, `restore_phase`,
`process_temperature`, `process_uptime_ms`, `duration_ms` (monotonic),
`cache_status`, `signature_prefix` where applicable.

## Process temperatures (not interchangeable)

`PROCESS_COLD` · `PROCESS_WARM_SESSION_COLD` · `SESSION_WARM` ·
`PRESENTATION_RERUN` · `AUTH_RESTORE` · `GUEST_COLD`

## Summary event

`startup_trace_summary` — compact non-PII totals for auth / provider / player /
league / trade / briefing / compose / presentation + cache statuses +
duplicate / post-READY counts + slowest stage.

## Instrument owners

| Area | What is measured |
| --- | --- |
| Auth/storage | mount→receive, JS read/emit (existing handshake), payload apply stages |
| Provider | Sleeper categories via `provider_timing` (no league/user ids) |
| Prepared frame / league / trade | process hit/miss + same-signature duplicate detection |
| Briefing assembly | total + injury / waiver / tiles / organization / snapshot substages |
| Compose | process memo phases (existing) + note_build |
| Reruns | `startup_run` + `run_cause` (gated print when diagnostics off) |
| Post-READY | `post_ready_rebuild` if football rebuilds after complete |

## Capture

```bash
set DYNASTYGM_STARTUP=1
# reproduce scenarios A–H
python scripts/report_startup_waterfall.py logs.txt
python scripts/diagnose_tail_latency.py logs.txt
```

Architecture-encoded synthetic extremes (not live production):

```bash
python scripts/diagnose_tail_latency.py --synthetic
```

## Evidence-based owners

| Band | Typical owners |
| --- | --- |
| Session warm revisit | Presentation only — server-side usually &lt;300 ms |
| Process warm + session cold | Auth restore / storage handshake + shell reruns |
| Process cold | Prepared frame + league/trade miss + briefing (~0.9–1.4s historically) + compose |
| &gt;10–15 s | Auth cascade + process-cold football + optional provider refresh; **plus** possible Render wake **before** Python instrumentation (**UNKNOWN** without host logs) |

### Synthetic sample (n=4 architecture extremes, not live)

From `diagnose_tail_latency.py --synthetic`:

| Milestone | median | p90 | max |
| --- | --- | --- | --- |
| loading dismissed | ~3000 | ~6500 | 6500 |
| first useful | ~5200 | ~12100 | 12100 |
| Game Plan ready | ~6000 | ~13800 | 13800 |
| Dashboard / interactive stable | ~6450 | ~15200 | 15200 |

Live production percentile tables require founder-captured `DYNASTYGM_STARTUP` logs on the always-on Render worker.

## Optimizations in this PR

1. Gate `startup_run` log spam when diagnostics are off (counter still increments).
2. Same-signature duplicate + post-READY rebuild detectors.
3. Briefing substage accounting + provider timing categories.
4. **No** football methodology / fingerprint TTL / trust / cache-staleness changes.

## Hosting / frontend boundary

In-process logs cannot prove container wake before `process_uptime_ms` origin.
If users see 10–15 s and summaries account ~6–8 s of Python work, classify the remainder as:

`UNEXPLAINED/gap — possible Render wake / Streamlit delivery / browser`

## Verdict

**TAIL LATENCY UNDERSTOOD** at the architecture / instrumentation level for
application-owned stages. Live production 15s outliers remain partially
**UNEXPLAINED** until host-level wake and browser delivery are measured on the
deployed topology.

Recommended next pass: **EXPERIMENTAL FEATURE REINCORPORATION AUDIT**.
