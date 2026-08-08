# DynastyGM UI Primitives

These primitives are the first reusable presentation layer above
`modules/design_tokens.py`. They are deliberately narrow: they render app-owned
structure and escaped text, while page modules retain routing, state, and business
logic.

## Shared contract

- All visual values resolve through semantic CSS custom properties.
- All selectors are scoped under `dg-ui-`; no Streamlit implementation selectors
  or global element selectors are used.
- User-controlled strings are escaped. Arbitrary child HTML is not accepted.
- Link actions accept only relative destinations and `http` or `https` URLs.
- Native Streamlit buttons remain caller-owned.
- Components wrap at 640px, maintain 44px action targets, expose visible focus,
  and disable optional motion under `prefers-reduced-motion`.

## Primitives

### Section header

`section_header_html(title, subtitle="", eyebrow="", trailing_action=None,
heading_level=2)` supports heading levels 2–4. The title is required; all other
regions are optional. Its trailing action is one safe link. It is for content
sections, not page titles, navigation, or interactive status.

### Content card

`content_card_html(body, variant="default", title="", metadata="", footer="")`
accepts escaped text regions only. Variants are `default`, `elevated`,
`interactive`, `premium`, `experimental`, and `warning`. Interactive indicates
an actual safe-link destination and requires `action=(accessible_label, href)`;
the whole card then receives native link keyboard and focus behavior. Other cards
may use the same optional action when a single destination is appropriate. Cards
contain no recommendation or entitlement logic.

### Status badge

`status_badge_html(label, variant="neutral")` supports `neutral`, `information`,
`opportunity`, `success`, `caution`, `danger`, `premium`, and `experimental`.
Visible text and an accessible state label accompany every color treatment.
Badges are status, not controls or filters.

### Informational callout

Removed — unused in product surfaces. Prefer status badges, empty states, or
content cards for guidance.

### Empty-state panel

`empty_state_panel_html(title, explanation, kind=..., primary_action=None,
secondary_action=None, recovery_guidance="")` requires one of `no-data`,
`filtered-empty`, `unavailable`, or `error`. This keeps scarcity, filtering,
availability, and failure semantics distinct. It accepts at most two safe links
and does not perform retries itself.

### Action row

`render_action_row(primary_action, key=..., secondary_action=None,
destructive_action=None)` invokes caller-owned native Streamlit controls in
secondary, destructive, primary order inside a public horizontal container. The
caller supplies a unique key and owns labels, callbacks, disabled state, and
confirmation. The container wraps responsively; it never changes button behavior.

## Production proof

Only the Trade Hub entitlement summary uses a primitive in this phase. Its existing
post-Trust presentation data and exact summary copy are passed to an informational
or Premium callout. Recommendation visibility, grouping, Premium locking, routing,
and entitlement resolution remain unchanged.
