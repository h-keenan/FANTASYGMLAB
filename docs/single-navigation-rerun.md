# Single-rerun destination navigation

## Scope

This change covers the ordinary desktop sidebar and mobile destination-sheet
controls only. Authentication, saved-league switching, active-team switching,
Player Detail transitions, refresh actions, and other explicit state-transition
reruns remain unchanged.

## Flow

Previously, a desktop button's automatic rerun entered its body, queued the
route, wrote the query parameter, and called `st.rerun()`. The destination was
therefore rendered by a second script run. Mobile already used a callback, but
only queued the route.

Both controls now call the same callback orchestration. The callback:

1. records the existing interaction marker;
2. queues the pending route and scroll-reset metadata;
3. commits `platform_nav_page` before Streamlit begins its normal widget rerun.

The existing route initialization consumes the pending route, derives its
navigation group, and synchronizes the public `page` query parameter. No
explicit rerun is called by either ordinary destination control.

## Explicit reruns retained

The source inventory confirmed separate reruns for authentication restoration
and transitions, saved-league restoration and switching, Player Detail and
other cross-surface handoffs, manual data refresh, and other state transitions.
None were removed or altered.

## Controlled local evidence

The committed measurement script uses Streamlit AppTest with
`DYNASTYGM_RUNTIME_TRACE=1`; it emits only sanitized aggregate output. Ten
Dashboard-to-My-Team actions produced one automatic script run, one completed
trace report, and zero explicit-rerun events per action. Median server time was
100.4 ms (97.6–178.5 ms), with 79 messages and 289,736 protobuf bytes. These
figures are local structural measurements, not browser or production latency.

A representative pre-change action emitted an explicit-rerun event after
105.1 ms and then completed the destination in a second 148.6 ms run (at least
253.7 ms combined server time). The completed destination report contained 78
messages and 289,672 bytes; the old tracer did not retain the discarded partial
run's message/byte totals, so an exact combined payload comparison is not
available.

The controlled path My Team → Waivers → League Overview → Trade Hub → Dashboard
kept route and query state aligned with no explicit navigation-rerun events.
Pages requiring a selected league can terminate with `st.stop()` before the
footer emits a completed report; the measurement distinguishes one AppTest
action script run from zero completed footer reports in that case.

Desktop and mobile callbacks both resolved My Team correctly. Direct query
links survived refresh, malformed routes fell back to Dashboard, and simulated
back/forward query changes restored Dashboard/Waivers correctly. A real browser
History API and paint-timing check remains manual because AppTest does not
implement browser history or rendering.

## Reproduction

```powershell
$env:DYNASTYGM_RUNTIME_TRACE = "1"
python scripts/measure_navigation_reruns.py --samples 10
Remove-Item Env:DYNASTYGM_RUNTIME_TRACE
```
