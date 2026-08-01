# Production interaction latency investigation

Date: 2026-07-31  
Base: `main` at `091cb49908ec6740678a1f0a1447f9847f6415b4`

## Decision

No production optimization path was activated. None of shared Render Key Value,
a background worker, a request-path change, or further interaction isolation
met the evidence gate without adding unmeasured operational risk.

The measured lightweight-control floor is predominantly Streamlit frontend
reconciliation rather than Python. Native/local controls are already isolated:
the local disclosure measured 33.4 ms median and the navigation popover 42.0 ms.
A trivial Streamlit state rerun measured 106.7 ms in Chromium while its Python
work measured 1.8 ms. An already-prepared modal measured 131.6 ms in Chromium
and 3.2 ms in Python. Moving these already-local controls to another Python
cache cannot remove that residual.

## Correlated production timeline

Runtime trace schema v3 provides two anonymous identifiers:

- `session_correlation_id`: stable for a Streamlit session;
- `correlation_id`: unique to one script-run span.

It records only structural timings. It never records identities, league IDs,
URLs/query parameters, tokens, cookies, payloads, player names, or exception
messages. The application process can observe Streamlit script-run start, app
import duration, public-player completion, authentication restoration, profile,
entitlement, saved-league restore, categorized external time (including
Sleeper), shared context, route calculation, server rendering, and trace
completion.

Render request receipt and Render process-ready time occur outside the Python
application and are explicitly marked unobservable in the report. They must be
paired from Render events rather than guessed from app timestamps.

| Boundary | Local cold median | Local warm median | Production evidence |
|---|---:|---:|---|
| App import + process/AppTest completion | 3,461.2 ms | n/a | Render start event required |
| Streamlit server rerun | 941.3 ms | 110.8 ms | trace v3 |
| Public players complete | 824.1 ms | 30.0 ms | trace v3 |
| Auth bridge complete (logged out fixture) | 825.5 ms | 31.0 ms | controlled account required |
| Profile complete (logged out fixture) | 826.6 ms | 31.9 ms | controlled account required |
| Entitlement complete (logged out fixture) | 827.1 ms | 32.0 ms | controlled account required |
| League restore complete (logged out fixture) | 828.2 ms | 32.9 ms | controlled league required |
| League shell complete | 894.1 ms | 99.5 ms | trace v3 |
| Route calculation complete | 902.5 ms | 106.8 ms | trace v3 |
| Server trace complete | 907.5 ms | 111.0 ms | trace v3 |
| Public HTTPS TTFB | n/a | n/a | 467.9 ms median, 398.9–836.4 ms range |

Cold AppTest wall time was 2,713.6 ms median and warm AppTest wall time was
1,205.5 ms. AppTest is not a browser; its residual is not labeled as network or
paint. Production HTTPS samples cover the anonymous HTML shell only, not the
websocket application run.

## Browser interaction floor

Ten loopback Chromium samples at 390x844:

| Interaction | Browser median | Python median | Dominant residual |
|---|---:|---:|---:|
| Local HTML disclosure | 33.4 ms | 0 ms | layout/paint |
| Native navigation popover | 42.0 ms | 0 ms | Streamlit frontend |
| State-only Streamlit control | 106.7 ms | 1.8 ms | 104.9 ms reconciliation/transport |
| Already-prepared modal | 131.6 ms | 3.2 ms | 128.4 ms reconciliation/paint |

These loopback results exclude public internet latency. They demonstrate that
the smallest server-backed interaction is already at the 100 ms product target
before production network latency. They do not prove Render is slow.

## Controlled collection procedure

Enable `DYNASTYGM_RUNTIME_TRACE=1` for one short controlled window, deploy, and
restart. Use only synthetic/controlled accounts and leagues. Capture only lines
beginning `DYNASTYGM_RUNTIME ` or `DYNASTYGM_RUNTIME_RERUN ` plus Render's
process start/ready timestamps. Disable the flag and restart after collection.

For each action, record the browser Performance API's monotonic click/navigation
start and visible-target completion, and the two anonymous IDs from the matching
trace. Do not export browser storage, network headers, request URLs, console
errors, screenshots, or raw page content.

1. **Sleeping-service cold launch:** allow the service to reach its configured
   idle state; record Render process-start/ready events; open `/`; wait for the
   first useful Dashboard target; retain one trace only.
2. **Already-awake first load:** verify `/\_stcore/health`, create a fresh
   incognito browser session, load `/`, and retain the first completed trace.
3. **Warm navigation:** perform one prewarm navigation, then make ten controlled
   Dashboard/My Team transitions; correlate each visible page title.
4. **Navigation orb:** open and close the orb ten times. This should produce no
   completed server trace; any trace is a regression.
5. **Player Quick View:** prewarm player data, open ten controlled dossiers, and
   correlate the visible dossier marker with traces.
6. **Trade Detail:** prewarm a controlled Trade Board, open ten existing trade
   details, and correlate the dialog marker. Do not generate new trades during
   the interaction-floor sample.

Run locally with:

```text
python -m streamlit run scripts/interaction_latency_harness.py --server.headless true --server.port 8512
python scripts/measure_streamlit_interaction_floor.py --base-url http://127.0.0.1:8512 --samples 10
python scripts/measure_local_streamlit_e2e.py --samples 10
```

## Shared-cache feasibility

| Candidate | Current cost/hit | Size | Expected shared read | Invalidation | Privacy | Restart benefit | Decision |
|---|---|---:|---:|---|---|---|---|
| Normalized public-player snapshot | 503.4 ms cold; 1.8 ms warm | 388,808 B | Unmeasured; network plus decode | source fingerprint + schema | public | at most cold-only | Reject: local disk snapshot already survives restart; decode/eligibility dominates and expected gain is below 500 ms |
| Source fingerprint | negligible | under 1 KB | network likely slower | source file metadata | public | negligible | Reject |
| League-independent ranking inputs | already derived from public snapshot | about 0.9 MB in memory | unmeasured | engine/schema/source versions | public | cold-only | Reject: settings-dependent consumers and no measured standalone delay |
| Static lookup tables | negligible | small | network slower | code version | public | negligible | Reject |
| Sanitized Sleeper envelopes | network-variable | variable | potentially lower | endpoint + TTL + schema | customer/league scoped | restart benefit possible | Reject: isolation/freshness risk and no production call distribution |

No entitlement, authentication, Trust, recommendation, or mutable session state
is eligible for shared caching. A Render Key Value instance would add a paid
managed service, network dependency, environment secret, monitoring, and new
failure mode. No repository or Render configuration was added.

## Background-worker feasibility

The only plausible worker candidate is public snapshot construction. It is
deterministic and versionable, but a committed/disk snapshot already provides
the artifact and the web process still pays deserialization/eligibility work.
Its measured cold boundary is about 503 ms and its warm hit is 1.8 ms. A worker
would add a paid service and shared artifact transport without a proven >500 ms
gain. League, roster, recommendation, Trust, entitlement, and authentication
work is intentionally ineligible. No worker was added.

## Product targets and conclusion

- Local UI control under 100 ms: native/local controls meet it; server-backed
  Streamlit controls narrowly do not.
- Warm page navigation under 500 ms: server Python is within target locally;
  deployed browser completion remains unmeasured.
- Warm application return under 750 ms: public HTML TTFB is within target in
  the sample; websocket/content completion is not yet proven.
- Useful shell under 3 seconds: local AppTest wall meets this narrowly; an
  observed 15-second closed-app production launch cannot be apportioned without
  Render start/ready events.
- Complete cold launch under 5 seconds: local process/AppTest meets it; Render
  sleep is still an external unknown.

Recommendation: remain on Streamlit and collect one controlled deployed trace
window before committing to infrastructure. If authenticated deployed browser
traces confirm the ~100 ms framework floor plus ~470 ms public path on every
interaction, the next phase should be an incremental frontend migration proof
of concept for one high-frequency local interaction—not another Python cache.
