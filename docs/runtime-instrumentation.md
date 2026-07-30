# Runtime instrumentation

Runtime tracing is disabled by default and does not install wrappers or decorate
production functions unless the process starts with:

```text
DYNASTYGM_RUNTIME_TRACE=1
```

Each completed Streamlit rerun writes one sanitized JSON record prefixed with
`DYNASTYGM_RUNTIME`. Records contain no league IDs, roster IDs, usernames,
emails, URLs, tokens, cache keys, or request payloads.

The record includes:

- route and total rerun/page time;
- inclusive phase and function timings;
- requested duplicate-computation call counts;
- context-local DataFrame copy and merge counts;
- the 12 largest observed DataFrames by shallow estimated memory;
- external request counts and elapsed time by sanitized source;
- explicit Sleeper and RSS/news request counts.

The requested route names are `dashboard`, `my_team`, `trade_hub`, `waivers`,
`player_detail`, and `rankings` (reported as `league_overview` by the
summarizer).

## Capture

Enable the flag in a production-like process, exercise representative cold and
warm reruns for each page, and retain the `DYNASTYGM_RUNTIME` log lines. Do not
enable the flag permanently; the extra observation work is intended for bounded
measurement windows.

## Summarize

```powershell
python scripts/summarize_runtime_traces.py runtime.log -o runtime-summary.json
```

The summary contains per-page min/mean/p95/max totals, inclusive phase and
function totals, duplicate call counts, DataFrame operations, external request
counts, largest frames, and the five highest observed duplicate/external-latency
opportunities.

Function and phase timings are inclusive and may overlap. DataFrame memory is a
shallow estimate so that tracing does not perform expensive deep object scans.
The pandas, Requests, and RSS hooks are installed only in an enabled process;
their counters are isolated to the active rerun with `contextvars`.
