# Startup, authentication restoration, routing, and loading investigation

Date: 2026-07-30
Base: `trust/complete-production-integration` at
`7375a0e3eff795bb82558c22513764983dd38148`

## Executive finding

The application does not currently have a coordinated loading screen. It
progressively emits the global black shell, hero, and a native inline Streamlit
spinner while public player data loads. Authentication restoration then uses an
asynchronous browser component and explicit reruns; saved-league restoration
may request another explicit rerun. Each script run begins by rebuilding the
same shell and inline spinner.

This explains both reported symptoms:

- the loading treatment looks unfinished because it is an inline status element
  on the normal black application canvas, not a viewport loading layout;
- authenticated startup visibly moves through multiple intermediate trees
  because browser storage, Python auth restoration, durable-session saving, and
  saved-league restoration settle across separate runs.

No authentication, entitlement, loading, routing, or CSS behavior was changed.
The only production additions are disabled-by-default structural trace markers.

## Environment and evidence limits

Measured:

- Windows local host;
- Python virtual environment and Streamlit AppTest;
- repository public-player data;
- logged-out Dashboard with Supabase unconfigured;
- ten new-process runs and ten same-process warm runs;
- opt-in `DYNASTYGM_RUNTIME_TRACE=1`;
- static control-flow, component-JavaScript, CSS, and state-mutation inspection.

Not available:

- a controlled Supabase developer account and durable browser token;
- a controlled saved league in an authenticated browser;
- deployed logs or Render process metrics;
- browser screenshots and DOM geometry because the installed controlled-browser
  runtime could not initialize in this environment.

No customer account, organic traffic, user/league/player identifier, token,
cookie, query value, DOM text, or raw log was retained. Authenticated rerun
counts below are structural minima/ranges, not fabricated browser samples.

## Complete startup sequence

```text
Browser / Streamlit        app.py                         browser auth component       Supabase / league
        |                    |                                      |                       |
        | request script run |                                      |                       |
        |------------------->| set page config                      |                       |
        |                    | emit APP_CSS + founder CSS + hero    |                       |
        |                    | emit inline "Loading player data"    |                       |
        |                    | load/validate public player frame    |                       |
        |                    | render 1 x 1 auth bridge ------------>| read localStorage     |
        |                    |                                      | trigger stored/status |
        |<-------------------| partial tree                         |                       |
        | component rerun    |<-------------------------------------|                       |
        |------------------->| rebuild CSS + hero + spinner         |                       |
        |                    | apply/refresh stored auth ----------------------------------->|
        |                    | queue durable save                   |                       |
        |                    | explicit st.rerun()                  |                       |
        | explicit rerun     | rebuild CSS + hero + spinner         |                       |
        |------------------->| render bridge "save" ---------------->| write localStorage    |
        |                    | load profile/entitlement ------------------------------------>|
        |                    | restore saved league ---------------------------------------->|
        |                    | [optional explicit st.rerun()]       |                       |
        | optional rerun     | rebuild CSS + hero + spinner         |                       |
        |------------------->| resolve active league/context        |                       |
        |                    | restore query/session route          |                       |
        |                    | request navigation scroll reset      |                       |
        |                    | render destination + footer          |                       |
        |<-------------------| final usable tree                    |                       |
```

The component's `setTriggerValue()` call is an asynchronous Streamlit component
event and initiates a normal rerun. The Python path then explicitly calls
`st.rerun()` after successful auth restoration. Its queued `save` command emits
another component status event. A default saved league adds a second explicit
Python rerun. Streamlit may coalesce component behavior depending on timing, so
the exact authenticated count requires a controlled browser trace.

## Rerun and visible-state counts

| Path | Completed/partial runs supported by evidence | Visible loading/shell states |
| --- | ---: | ---: |
| Logged out, no league | 1 measured | inline loading state, then final page |
| Durable auth, no saved league | minimum 3; commonly 3-4 structurally | initial shell, storage-result shell, authenticated shell, final |
| Durable auth plus saved league | minimum 4; up to 5 structurally | adds a league-restoration shell |

The required transition is the browser component event that returns storage to
Python. The explicit auth-restored rerun and optional saved-league rerun are
separate orchestration transitions. The durable-save status event may add
another automatic rerun. No asynchronous Python auth task exists: the
asynchrony is the browser component boundary.

## Measured logged-out timeline

Medians from ten samples; times are relative to the start of one script run.
Directional p95 is an upper small-sample observation, not a service objective.

| Event | Cold median | Cold directional p95 | Warm median | Warm directional p95 |
| --- | ---: | ---: | ---: | ---: |
| Public player load complete | 780.0 ms | 791.8 ms | 23.6 ms | 25.9 ms |
| Auth storage bridge complete | 781.0 ms | 793.1 ms | 24.4 ms | 26.8 ms |
| Profile lookup complete | 781.8 ms | 793.9 ms | 25.1 ms | 27.5 ms |
| Entitlement lookup complete | 782.0 ms | 794.3 ms | 25.4 ms | 27.8 ms |
| Saved-league restore complete | 782.8 ms | 795.0 ms | 26.1 ms | 28.5 ms |
| Session initialization complete | 783.2 ms | 795.5 ms | 26.6 ms | 28.9 ms |
| League/shell data complete | 843.2 ms | 857.3 ms | 86.5 ms | 101.7 ms |
| Route restoration complete | 847.5 ms | 862.4 ms | 90.5 ms | 105.7 ms |
| Page calculation complete | 852.0 ms | 866.9 ms | 94.3 ms | 109.5 ms |
| Elements/rerun complete | 855.9 ms | 870.6 ms | 97.8 ms | 112.7 ms |

Process-to-AppTest-completion median was 3,145.2 ms cold. AppTest wall median
was 2,485.4 ms cold and 1,116.8 ms warm; its polling/synchronization residual is
not labeled browser rendering time. Server rerun median was 855.8 ms cold and
97.4 ms warm.

Each logged-out run emitted 67 elements, 76 cold/75 warm messages, and
287,662/287,544 uncompressed protobuf bytes. There were zero external requests
because Supabase and a league were unavailable.

### Representative warm timeline

```text
  0.0 ms  rerun starts; CSS, hero, inline spinner begin emitting
 23.6 ms  public player frame ready
 24.4 ms  auth bridge returns (unconfigured/no restoration)
 25.1 ms  profile lookup boundary
 25.4 ms  entitlement resolved
 26.1 ms  saved-league restoration checked
 26.6 ms  session initialization complete
 86.5 ms  common league/shell work complete
 90.5 ms  route resolved and scroll reset requested
 94.3 ms  page calculation complete
 97.8 ms  final element tree complete
```

## Authentication and state activity

Per completed startup run, the production path invokes:

- one durable-auth bridge render;
- one profile refresh adapter call (network guarded by its session loaded key);
- one effective-entitlement resolution;
- one saved-league auto-resume check;
- two active-league-context resolutions in the common path;
- one query-route reconciliation.

Successful durable restoration writes the auth session, user, email, account
mode, and a pending durable-save payload. The bridge also records only safe
status/reason/result/refreshed fields. Profile loading writes its per-user guard,
profile/status, and optional error state. Entitlement writes one canonical
effective-entitlement key. Saved-league restoration writes the cached saved
rows and selected league/context keys. Exact runtime write counts depend on
whether tokens refresh, a profile exists, and a default league exists; those
branches were not exercised without a controlled account.

Query parameters are read during route restoration and written once only when
the normalized current page differs. A successful saved-league resume can also
write the preserved route before its explicit rerun.

## Loading-screen root cause

There is no full-height loading container:

- `st.spinner("Loading player data...")` is an intrinsic inline Streamlit
  element placed after `.app-hero`;
- neither `APP_CSS` nor `FOUNDER_BETA_UX_CSS` targets `stSpinner`;
- the `.block-container` has only 0.8 rem top padding on desktop and 0.75 rem
  under the mobile breakpoint;
- the black/graphite appearance is the intentional global `.stApp` background;
- the spinner is recreated at the beginning of every restoration rerun;
- navigation scroll reset is not emitted until route restoration, after player,
  auth, profile, entitlement, league, and shell work.

Therefore the reported "loading screen" is actually a partially built normal
page. On a restored/refreshed session, browser scroll can remain at the prior
page position while the short top-of-document spinner exists; the reset arrives
only near the end of the run. That makes the top inline status text appear
clipped or outside the visible viewport. Small/mobile viewports use the same
inline geometry and less horizontal/top padding, so they do not gain a centered
or viewport-safe treatment.

Static viewport audit:

| Viewport | Loading positioning | Top spacing | Responsive finding |
| --- | --- | ---: | --- |
| Desktop | normal document flow after hero | 0.8 rem container top | no centering/min-height |
| Tablet (<=900 px) | same flow | 0.75 rem from earlier mobile rule | large bottom safe-area rules do not help loading |
| Mobile (<=900 px) | same flow | 0.75 rem; 0.72 rem side override | no loading-specific viewport/safe-area rule |

Pixel dimensions, actual scroll offset, paint time, and screenshots remain
unmeasured because controlled browser initialization failed. This limitation
blocks claims about exact clipped pixels, not the code-level positioning cause.

## Startup state machine

```text
PROCESS_START
  -> PUBLIC_DATA_LOADING
  -> AUTH_STORAGE_PENDING
       -> AUTH_GUEST ------------------------------+
       -> AUTH_RESTORED -> DURABLE_SAVE_PENDING    |
  -> PROFILE_PENDING                              |
  -> ENTITLEMENT_READY                            |
  -> LEAGUE_RESTORE_PENDING                       |
       -> NO_LEAGUE -------------------------------+
       -> LEAGUE_SELECTED -> CONTEXT_PENDING
  -> ROUTE_RESTORE_PENDING
  -> PAGE_BUILDING
  -> INTERACTIVE
```

`PUBLIC_DATA_LOADING`, `AUTH_STORAGE_PENDING`, and the global shell are entered
again on every component or explicit rerun. `PROFILE_PENDING` is revisited but
its network request is guarded. `LEAGUE_RESTORE_PENDING` is revisited after a
successful auto-resume. The final route is correct because query/session route
normalization occurs after these transitions.

## Exactly one recommended implementation

### Add a session-scoped startup coordinator

Introduce one explicit startup coordinator with immutable phase results for:
browser-auth resolution, profile/entitlement readiness, saved-league readiness,
and route readiness. While these phases settle, render one viewport-stable,
centered loading shell. Mount the normal hero/sidebar/page tree only after the
coordinator reaches `PAGE_READY`.

Within that same coordinator, consume the browser component result, profile,
entitlement, saved league, and route state before requesting the one final
application rerun. Do not rerun immediately after auth and then independently
again after league restoration. The browser component event remains necessary;
auth policy and token handling remain unchanged.

Why this is the first recommendation:

- it directly addresses both measured structural causes rather than merely
  restyling the inline spinner;
- it removes one or two discarded partial application trees on restored
  sessions;
- it gives desktop/tablet/mobile one stable loading geometry;
- it leaves player loading, caches, auth semantics, entitlement, and routing
  contracts intact.

Expected server-side saving on a warm restored startup is approximately one to
two common-path reruns: directionally 97-195 ms locally, plus avoiding
approximately 288-575 KB of repeated uncompressed Streamlit messages. External
Supabase latency is not included. The larger UX benefit is reducing roughly
three-to-five visible intermediate states to one stable loading state followed
by the final destination.

Explicit implementation exclusions:

- no authentication or refresh-token rewrite;
- no entitlement/Premium change;
- no cache or player-loader change;
- no route contract or navigation change;
- no broad CSS redesign;
- no Trust, trade, valuation, ranking, Team Needs, or page-content change.

Rollback would remove the coordinator boundary and restore the current
independent auth/league reruns and inline spinner.
