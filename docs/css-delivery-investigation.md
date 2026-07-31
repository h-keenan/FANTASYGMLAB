# Global CSS delivery investigation

## Verdict

The global CSS is serialized and sent on every full rerun, but the controlled
server-side experiment does not establish it as a material browser-visible
bottleneck. Replacing the two global style blocks with tiny placeholders removed
about 272 KB of uncompressed ForwardMsg payload while improving median server
time by only 10–13 ms on completed routes. AppTest wall time did not improve
materially. Browser transfer, style-recalculation, layout, and paint evidence
could not be collected because the controlled browser connection was unavailable.

The CSS should therefore not be changed yet. In particular, a session-state
"emit once" guard is not valid: full Streamlit reruns redraw elements, so the
style element disappears on the next rerun.

## Inventory

| Source | Normalized UTF-8 bytes | Injection | Scope | Classification |
| --- | ---: | --- | --- | --- |
| `modules/app_styles.py::APP_CSS` | 266,067 | `inject_global_styles` → `st.markdown(..., unsafe_allow_html=True)` | Before routing, every full rerun | Static |
| `modules/ux_polish_styles.py::FOUNDER_BETA_UX_CSS` | 6,426 | Same | Before routing, every full rerun | Static |
| `modules/live_draft_ui.py::ranking_card_styles_html()` | 1,473 | Page-local `st.markdown` | Live Draft ranking surfaces | Static |
| `modules/live_draft_ui.py` inline ranking style block | 1,742 | Page-local `st.markdown` | Live Draft connected ranking surface | Static |
| Inline `style=` attributes | Small per element | App-owned HTML fragments | Relevant component/page only | Dynamic widths or presentation values |

The two global blocks total 272,493 normalized UTF-8 bytes. They contain 31
media-query sections (29 plus 2), no `url(...)` references, no third-party font
imports, and no runtime interpolation. Dynamic values are confined to small
component HTML attributes such as progress widths; they do not require global
stylesheet re-emission.

Selector token analysis found 1,284 unique selector tokens in `APP_CSS` and 71
in the founder layer. Repeated occurrences are common because of media queries,
state variants, and later overrides: 1,423 repeat occurrences in `APP_CSS` and
8 in the founder layer. Thirty selector tokens occur in both global blocks
(including root/style parser artifacts); these are overlaps, not proven
equivalent declarations. A literal-source scan found 216 class tokens without a
literal reference outside the stylesheets, but generated class-name variants
make that only a candidate list, not proof of dead CSS.

## Serialization and transmission

Ten repetitions on each controlled action produced byte-identical style hashes
and stable ordering:

- APP_CSS normalized hash:
  `eeda7af001797767e4eab1c68e8f8bf611c0aeaf06d3896e02f4192a8f07c5c4`
- Founder CSS normalized hash:
  `4d6b0ab18d3c05c00c80c9e7f3861b53ea8ad72c171b34f92c01311eabaa4e3d`
- APP_CSS ForwardMsg: 266,169 protobuf bytes
- Founder CSS ForwardMsg: 6,522 protobuf bytes

The instrumented `ScriptRunContext.enqueue` sees both Markdown messages on every
completed rerun. Streamlit 1.58 serializes each ForwardMsg and queues it for
`WebSocket.send_bytes`; there is no content-hash deduplication in that path.
The local configuration leaves `server.enableWebsocketCompression` at its
default `false`, so the controlled local WebSocket does not negotiate
per-message deflate. Deployment compression was not inspected and remains
unknown. For scale only, normal gzip/zlib compression reduces the two CSS bodies
from 272,493 bytes to about 37.3 KB; this is not a measured wire size.

Streamlit documents that a full rerun redraws application output. The two style
elements retain positions one and two and replace the prior elements rather
than append indefinitely. Replacement delivers their bodies again; whether the
browser can avoid any parsing or recalculation for identical text is unmeasured.

## Controlled results

All figures below are local logged-out Streamlit AppTest measurements with ten
samples per action. Directional p95 values are not production service levels.
Routes requiring a selected league call `st.stop()` before the existing footer
emits its completed runtime report; their element hashes and route/query state
were still observed, but server/message totals are unavailable.

### Current production path

| Action | Server median ms | Messages | Protobuf bytes | CSS messages |
| --- | ---: | ---: | ---: | ---: |
| Dashboard warm | 101.0 | 75 | 287,544 | 2 |
| Dashboard → My Team | 103.0 | 79 | 289,736 | 2 |
| My Team → Waivers | unavailable after `st.stop()` | unavailable | unavailable | 2 elements |
| Waivers → League Overview | 103.4 | 79 | 289,892 | 2 |
| League Overview → Trade Hub | unavailable after `st.stop()` | unavailable | unavailable | 2 elements |
| Trade Hub → Dashboard | 102.0 | 77 | 289,088 | 2 |

### Temporary tiny-CSS experiment

This experiment monkeypatched the public injection helper inside the measurement
process only. It was never committed as production behavior.

| Action | Server median ms | Protobuf bytes | Median server delta |
| --- | ---: | ---: | ---: |
| Dashboard warm | 88.2 | 15,081 | -12.8 ms |
| Dashboard → My Team | 92.2 | 17,273 | -10.8 ms |
| Waivers → League Overview | 91.2 | 17,429 | -12.2 ms |
| Trade Hub → Dashboard | 90.7 | 16,625 | -11.3 ms |

Message counts did not change because tiny placeholders still occupied the same
two element positions. AppTest wall medians changed by only -5.1 to +4.0 ms,
which is noise relative to its approximately 1.15-second polling behavior and
is not browser latency.

### Temporary first-render-only experiment

After the initial controlled render, APP_CSS was omitted while the founder block
continued to be emitted. Payload fell by 266,169 bytes and server medians
improved by 10–13 ms, similar to the tiny experiment. The resulting element tree
contained only the founder style block. This proves a session-state guard would
lose APP_CSS on a full rerun and fail visual equivalence; it is not a viable
implementation.

## Browser and visual evidence

The controlled browser facility failed during connection setup, so no credible
WebSocket-frame, response-to-DOM, style recalculation, layout, paint, LCP, or
click-to-visible measurements were produced. No findings are fabricated.

No screenshots were committed. A visual baseline still requires controlled
fixtures at desktop viewports for Dashboard, My Team, Trade Hub, Waivers, League
Overview, and Player Detail, plus mobile Dashboard, My Team, and Trade Hub.
Capture before/after images with stable viewport, device scale factor, font
availability, fixture data, and animation settings; retain only pixel/perceptual
diff metrics if screenshots contain identifiers.

Manual Chrome DevTools collection procedure:

1. Start local Streamlit with tracing and a controlled fixture.
2. Record Chrome version, viewport, DPR, cache state, and throttling.
3. In Network, preserve the `_stcore/stream` WebSocket and export only aggregate
   frame timestamps/sizes, never payloads.
4. In Performance, record a destination click and extract click-to-frame,
   frame-to-DOM, Recalculate Style, Layout, Paint, and usable-content marks.
5. Repeat ten times for current, temporary tiny, and temporary first-only
   processes; never mix processes or cache conditions.
6. Validate representative desktop/mobile screenshots before considering any
   delivery change.

## Supported delivery options

| Option | Avoids retransmission? | Correctness and operational assessment |
| --- | --- | --- |
| Current `st.markdown` injection | No | Supported and rollback-free; sends both blocks each full rerun. |
| Read CSS from a local file then inject | No | Changes source organization only; same Markdown payload. |
| Session-state injection guard | Yes, by omission | Unsupported behaviorally: full reruns remove the style element, refresh starts a new page, and appearance breaks. |
| Placeholder/container reuse | No | Public API, but full reruns still redraw and transmit replacement content. |
| Custom component | Not for parent styling | Component CSS is isolated; styling the parent would require unsupported DOM access and adds complexity/security risk. |
| Streamlit static serving plus same-origin `<link>` | Potentially, through browser cache | Publicly supportable with static serving, but changes deployment/configuration and needs CSP/cache/browser validation; excluded here. |
| Split global/page CSS | Reduces some payload | Supported, but requires selector ownership and visual-regression work; it does not eliminate global retransmission. |
| Deduplicate rules | Reduces payload | Supported, but cascade order makes it visually risky until declaration-level equivalence and screenshots are proven. |
| Separate dynamic tokens | Minimal benefit here | Global blocks are already static; dynamic inline widths are small and page-local. |

No option uses private Streamlit APIs. Multi-session isolation is unchanged by
the committed instrumentation because trace state is context-local and records
only hashes, sizes, ordinals, and counts. No CSS text, user data, route
identifiers, or page content is logged.

## Decision and next phase

CSS accounts for 94–95% of uncompressed server-enqueued payload, but removing it
saved only about 11–13 ms of server time and did not materially change AppTest
wall time. Browser-visible contribution is unmeasured. Under the 50 ms decision
rule, a production CSS delivery change is not justified.

Exactly one recommended next optimization is a behavior-preserving CPU-profile
and mechanical optimization of dynamic Trust enforcement, the largest remaining
measured server-side boundary (about 321 ms median in the prior controlled
measurements). The phase must preserve Trust inputs, rules, diagnostics, output,
and post-cache boundaries, and should stop if exact equivalence cannot be shown.
Expected `app.py` impact is zero.

Rollback for this investigation is a single instrumentation commit revert. The
measurement helper is disabled unless `DYNASTYGM_RUNTIME_TRACE=1`; normal CSS
injection and production appearance remain unchanged.

## References

- [Streamlit execution flow](https://docs.streamlit.io/develop/api-reference/execution-flow)
- [Streamlit app model](https://docs.streamlit.io/get-started/fundamentals/summary)
- [Streamlit element replacement](https://docs.streamlit.io/develop/concepts/design/animate)
- [Streamlit fragments and full-rerun redraw behavior](https://docs.streamlit.io/develop/concepts/architecture/fragments)
