# Authenticated Dashboard visual-regression pass

## Executive result

This pass adds a deterministic, fixture-backed Streamlit harness for the
authenticated Dashboard top region. It exercises the production global styles,
league identity header, league hero, Dashboard orientation, Next Moves cards,
Free/Premium gates, League Pulse cards, shared primitives, and canonical modal
renderers without loading an account, token, customer league, or customer data.

The controlled browser connector could not initialize in the available
environment. Consequently, this pass does **not** claim pixel, geometry, paint,
contrast-ratio, browser-history, or focus-return measurements at specific
viewports. Streamlit AppTest supplied interaction and render-tree evidence. The
standalone harness is committed so the remaining browser checks can be repeated
locally without changing production authentication.

One high-confidence P2 defect was proven and corrected: the four orientation
steps were one caption-sized text node rather than a semantic list. The shared
content-card primitive now supports an optional escaped ordered list that uses a
two-column desktop and one-column mobile token-backed layout.

## Safe validation strategy

- Harness: `scripts/dashboard_visual_harness.py`
- Framework executed: Streamlit `AppTest`
- Production entry point: unchanged; the harness is never imported by `app.py`
- Data: fixed synthetic league, franchise, entitlement, recommendation, and
  League Pulse labels
- Authentication approximation: deterministic authenticated-ready context
  passed only to the production orientation visibility contract
- No auth session, access token, profile row, Supabase request, Sleeper request,
  player identity, roster identity, or customer identifier is used
- No production authentication bypass exists

Run the fixture manually:

```text
streamlit run scripts/dashboard_visual_harness.py
```

Run the structural interaction coverage:

```text
python -m pytest -q tests/test_dashboard_visual_harness.py
```

## State matrix

| State | AppTest | Browser pixels | Result |
|---|---:|---:|---|
| Startup shell before PAGE_READY | Yes | No | Dashboard tree absent |
| First authenticated Dashboard render | Yes | No | Correct order and content |
| Free, orientation visible | Yes | No | Free gates retained |
| Premium, orientation visible | Yes | No | Full fixture content; no prompts |
| Orientation modal open | Yes | No | One canonical dialog event |
| Orientation dismissed | Yes | No | Card removed on rerun |
| League A dismissed | Yes | No | Dismissal retained |
| Switch to League B | Yes | No | Orientation independently visible |
| Return to League A | Yes | No | Dismissal retained |
| Multiple Next Moves | Yes | No | Five synthetic items available |
| Limited Next Moves | Harness-ready | No | One synthetic item |
| Empty Next Moves | Yes | No | Explicit fixture-only empty message |
| League Pulse summary | Yes | No | Premium summary content present |
| League Pulse detail modal | Existing modal tests | No | Canonical adapter retained |
| Long league name | Yes | No | Render tree completes without exception |
| Keyboard action order | Yes | No | Primary, detail, dismiss order |
| Reduced motion | CSS contract | No | Existing media rule retained |

## Viewport matrix

The harness is ready for 1440×900, 1280×720, 390×844, and 360×800 capture.
No browser-rendered viewport is reported as completed because the controlled
browser failed before navigation. AppTest has no viewport, layout, paint, or
computed-style model.

The corrected ordered-list contract declares:

- two equal columns above the existing 640px primitive breakpoint;
- one column at or below 640px;
- token-based gaps, indentation, line height, and text color;
- `overflow-wrap: anywhere` for long labels.

These are structural guarantees, not a substitute for browser screenshots.

## Findings

### P0

None in the completed fixture-backed states.

### P1

None in the completed fixture-backed states. Modal dismissal reachability,
background inertness, and physical mobile overflow remain browser-validation
gaps rather than confirmed passes.

### P2

1. **Corrected — orientation steps lacked semantic and responsive structure.**
   The four steps were passed through the card's metadata field as one string.
   This weakened scanability, reduced screen-reader structure, and left narrow
   wrapping to an undifferentiated caption paragraph.

   Design System rules: clear hierarchy, progressive disclosure, semantic
   structure, mobile-first responsiveness, and token-only presentation.

   Correction: add an escaped `items` tuple to the canonical content card and
   render it as an ordered list with a two-to-one-column responsive contract.

No other P2 correction was made without rendered browser evidence.

### P3 and deferred observations

1. Confirm the native horizontal action-row wrapping at 390px and 360px.
2. Confirm modal close-control reachability and safe-area behavior at 360×800.
3. Measure the first viewport proportion occupied by hero plus orientation.
4. Review the repeated “Next Moves” language in hero and section heading in a
   real browser before changing copy.
5. Run automated contrast tooling against computed styles, not source tokens.

## Accessibility evidence

Verified structurally:

- orientation actions are native buttons with meaningful labels and help text;
- action order is Review My Team, How DynastyGM works, then Dismiss;
- modal content uses the canonical dialog path;
- orientation steps are now an ordered list rather than color-only or flattened
  metadata;
- all list text is escaped;
- 44px control token and visible focus rules remain present;
- reduced-motion rules remain present;
- state keys remain separate from modal and Trade Hub disclosure namespaces.

Not verified without a browser:

- computed contrast;
- physical touch-target geometry;
- focus restoration after modal close;
- background inertness while the modal is open;
- visible focus-ring clipping;
- screen-reader announcement behavior.

## Free and Premium behavior

The harness uses the same post-calculation presentation split as the production
Dashboard fixture:

- Free shows the limited Next Moves slice and Premium prompts only when fixture
  content is hidden.
- Premium shows the complete fixture Next Moves and League Pulse content with no
  upgrade prompts.
- Orientation rendering has no entitlement input and remains identical.

No entitlement helper, rule, limit, or production branch changed.

## Screenshot governance

No screenshots or raw browser traces were generated or committed. The harness
contains synthetic labels only and can be used for local screenshots with stable
state controls. If screenshots are captured later, keep them as CI artifacts or
sanitized local evidence unless the repository adopts a reviewed image-fixture
policy.

## Recommended next phase

Run one controlled browser-backed baseline of this committed harness at the four
required viewports, including keyboard focus and both modals. Only after that
baseline is clean should the first full page migration begin.
