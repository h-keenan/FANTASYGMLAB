# DynastyGM Design System

**Status:** Official specification, version 1.0
**Scope:** Visual and interaction language for future DynastyGM UI work
**Implementation status:** Documentation only; no current page or component is
automatically compliant because this document exists

## 1. Executive summary

The DynastyGM Design System establishes one authoritative language for presenting
football intelligence, recommendations, evidence, and actions. It is intentionally
derived from the application's latest semantic theme rather than inventing a new
brand direction.

The canonical identity is:

- a near-black, calm application shell;
- high-contrast white and silver information hierarchy;
- cyan for interaction and current context;
- teal for opportunity;
- yellow for user action;
- amber for caution;
- red for danger or invalid states;
- indigo for diagnostics and experimental information;
- restrained, sharp surfaces with minimal elevation;
- compact, evidence-led content that expands progressively;
- mobile-first stacking and keyboard-accessible interaction.

This specification does not redesign or migrate existing pages. Older visual tokens,
rounded/glass variants, page-specific colors, and duplicate component treatments are
migration debt. Future work must use the semantic contracts here and migrate
incrementally with visual-regression coverage.

## 2. Design philosophy

### Consistency creates confidence

The same meaning must look and behave the same on every page. A warning cannot be
amber on one surface and purple on another. A primary action cannot compete with
three equally prominent actions. Fantasy recommendations involve uncertainty;
visual inconsistency makes that uncertainty feel like unreliability.

### Clarity before density

Dynasty managers need depth, but not all at once. Lead with the decision, then the
evidence, then diagnostics. Dense data is acceptable when it supports a task and is
progressively disclosed.

### Actionability

Every primary surface should answer: “What should I understand or do next?” Visual
emphasis follows decision priority, not implementation complexity or data volume.

### Evidence before recommendation

Recommendations must be accompanied by enough reasoning, confidence, source state,
or Trust context to interpret them. Presentation must not imply certainty that the
underlying system does not provide.

### Minimal cognitive load

Use familiar component roles, concise labels, stable placement, and no more than one
dominant action in a local context. Do not make users decode decorative color,
unexplained abbreviations, or competing card treatments.

### Accessibility is a base requirement

Contrast, keyboard support, visible focus, semantic structure, zoom, reduced motion,
and touch targets are part of component acceptance—not a later polish phase.

### Mobile-first responsiveness

Design the information order at 320 CSS pixels first. Desktop may add columns and
context; mobile must not receive a compressed desktop table or lose task capability.

### Progressive disclosure

Summary first, supporting detail second, diagnostics last. Collapsed content must
have an accurate label and must never hide the only path to a required action.

### Trustworthy presentation

Visual tone is calm, direct, and non-promotional. Do not use urgency, glow, animation,
or “AI magic” aesthetics to make uncertain output appear more authoritative.

## 3. Token architecture

Future implementation should expose one semantic token layer. Components consume
semantic names, never page-specific hex values. Existing variables may be aliased
during migration, but new components must follow this contract.

Token categories:

1. **foundation:** shell, surfaces, text, dividers;
2. **interaction:** primary accent, hover, focus, disabled;
3. **meaning:** success, opportunity, action, caution, danger, information,
   diagnostic, Premium, experimental;
4. **structure:** spacing, radius, border, elevation, opacity, motion;
5. **type:** size, weight, line height, letter spacing.

## 4. Color system

### Foundation colors

| Token | Value | Use |
|---|---:|---|
| `color-bg` | `#050607` | Browser/application background |
| `color-shell` | `#090a0c` | App shell, sidebar, persistent chrome |
| `color-surface-primary` | `#0f1114` | Primary cards, dialogs, sheets |
| `color-surface-secondary` | `#15171b` | Supporting cards, grouped content |
| `color-surface-raised` | `#1b1e23` | Menus, selected controls, hover surface |
| `color-surface-muted` | `#0b0c0f` | Recessed lists and diagnostics |
| `color-text` | `#f8fafc` | Primary copy and values |
| `color-text-secondary` | `#e5e7eb` | Titles and supporting emphasis |
| `color-text-muted` | `#a8adb7` | Subtitles, captions, metadata |
| `color-divider` | `#2a2e35` | Default border and separator |
| `color-divider-strong` | `#41464f` | Active/raised separation |

Pure white may be used for a single highest-emphasis title or number. It must not
replace the normal text hierarchy across an entire component.

### Brand and interaction

| Token | Value | Meaning |
|---|---:|---|
| `color-primary` | `#67e8f9` | Current context, links, active navigation, primary focus |
| `color-primary-strong` | `#22d3ee` | Primary control fill/border where stronger contrast is required |
| `color-primary-soft` | `rgba(103,232,249,.14)` | Selected or highlighted background |
| `color-focus` | `rgba(103,232,249,.34)` | Three-pixel focus-ring color |

Cyan is not a generic decoration. Reserve it for interaction, selection, current
context, and the primary path.

### Semantic colors

| Token | Value | Use |
|---|---:|---|
| `color-success` | `#22c55e` | Completed, verified, healthy, valid |
| `color-opportunity` | `#14b8a6` | Trade/waiver upside, positive opportunity |
| `color-action` | `#facc15` | A recommended user action or Premium access |
| `color-warning` | `#f59e0b` | Caution, temporary pressure, degraded evidence |
| `color-danger` | `#ef4444` | Invalid, blocked, destructive, critical risk |
| `color-information` | `#67e8f9` | Neutral product guidance and current context |
| `color-diagnostic` | `#8b93ff` | Experimental, diagnostic, incomplete classification |
| `color-premium` | `#facc15` | Entitlement and upgrade language only |
| `color-experimental` | `#8b93ff` | Experimental feature status |
| `color-muted` | `rgba(229,231,235,.52)` | Neutral/inactive metadata |

Semantic color requires a text label or icon label. Never encode status by color
alone. “Positive” and “negative” are contextual: receiving more value may be
positive, but an increasing injury burden is negative. Labels must state the metric.

### Semantic soft backgrounds

Use 12–16% opacity over the dark shell:

- success: `rgba(34,197,94,.15)`;
- opportunity: `rgba(20,184,166,.14)`;
- action/Premium: `rgba(250,204,21,.14)`;
- warning: `rgba(245,158,11,.14)`;
- danger: `rgba(239,68,68,.15)`;
- information: `rgba(103,232,249,.12)`;
- diagnostic/experimental: `rgba(139,147,255,.12)`;
- muted: `rgba(229,231,235,.06)`.

Soft backgrounds support a border, stripe, icon, or chip; they must not become large
high-saturation fills.

### Borders

- default: 1px `color-divider`;
- strong/selected: 1px `color-divider-strong` or semantic color at 35–55% opacity;
- semantic panel: 3px left border plus default outer border;
- dominant mobile action: up to 5px left border;
- separators: 1px and full available content width;
- never use border thickness as the only state cue.

### Elevation and shadows

The shell should feel engineered and layered, not floating.

| Level | Shadow | Use |
|---|---|---|
| 0 | none | Inline lists, tables, flat groups |
| 1 | `0 2px 0 rgba(0,0,0,.32)` | Selected compact control |
| 2 | `0 3px 0 rgba(0,0,0,.34)` | Important panels and popovers |
| 3 | `0 8px 24px rgba(0,0,0,.46)` | Dialogs and blocking sheets |

Do not stack multiple outer shadows. A subtle `inset 0 1px 0 rgba(248,250,252,.035)`
may separate a raised dark surface. Glow is reserved for focus and must not be used
as persistent decoration.

### Corner radius

The canonical geometry is sharp and compact:

| Token | Value | Use |
|---|---:|---|
| `radius-none` | `0` | Connected rows, table edges |
| `radius-sm` | `0` | Badges, compact controls, semantic slabs |
| `radius-md` | `0` | Inputs, buttons, search, filters |
| `radius-lg` | `0` | Cards |
| `radius-panel` | `0` | Dialogs, drawers, large grouped surfaces |
| `radius-pill` | `2px` | Exceptional compact status tags only |

Do not use a pill shape for ordinary buttons, long labels, cards, or panels. Older
14–20px card radii are migration debt.

### Opacity

- primary content: 100%;
- secondary text: 78–86%;
- metadata: 62–72%;
- disabled text/control: 45–55%;
- decorative dividers: 8–18%;
- disabled components retain readable contrast and never drop below 45%;
- do not reduce an entire interactive card below 70%; change its state explicitly.

### Hover, active, disabled, and focus

- hover: increase border contrast and surface lightness slightly; movement is at most
  1px and optional;
- active/pressed: no scale animation; reduce surface elevation or darken fill;
- selected: use primary border/stripe plus `aria-current`, `aria-selected`, or
  equivalent state;
- disabled: remove hover, use `not-allowed` only when genuinely unavailable, explain
  why near the control;
- focus: 3px cyan ring with a visible offset or clear separation from the border;
- focus styling must work independently from hover;
- transitions are 120–180ms and disabled under `prefers-reduced-motion`.

## 5. Typography

Use the application's system sans-serif stack unless a separately approved,
performance-tested brand font is adopted. Numeric tables may use tabular numerals.
Do not introduce page-specific font families.

### Type scale

| Role | Size | Weight | Line height | Letter spacing | Alignment |
|---|---:|---:|---:|---:|---|
| Display | 32px / 2rem | 900 | 1.05 | -0.02em | Left |
| Page title | 24px / 1.5rem | 900 | 1.10 | -0.01em | Left |
| Section title | 18px / 1.125rem | 850 | 1.18 | 0 | Left |
| Card title | 14px / .875rem | 850 | 1.20 | 0 | Left |
| Subtitle | 14px / .875rem | 500 | 1.40 | 0 | Left |
| Body | 14px / .875rem | 450–500 | 1.45 | 0 | Left |
| Caption | 12px / .75rem | 500 | 1.35 | 0 | Left |
| Metadata | 12px / .75rem | 650 | 1.25 | .01em | Left |
| Button | 14px / .875rem | 750 | 1.15 | 0 | Center or left by control |
| Badge | 11px / .6875rem | 850 | 1.00 | .06em | Center |
| Numeric emphasis | 22px / 1.375rem | 900 | 1.00 | -0.01em | Right in tables; left in cards |

The minimum product text size is 12px. Form controls use at least 16px on mobile to
avoid iOS zoom. Uppercase is limited to kickers, short badges, and column headers;
never use it for sentences.

### Hierarchy rules

- One page title per page.
- Section headings descend in order; do not choose a heading level for appearance.
- Page subtitle is one concise sentence.
- Card title states the subject; metadata states supporting context.
- Numeric emphasis includes a visible label and units.
- Avoid centered body text except compact empty states or a deliberate standalone
  confirmation.
- Maximum comfortable prose width is approximately 70 characters.

## 6. Spacing

The canonical spacing scale is based on four pixels:

| Token | Value | Use |
|---|---:|---|
| `space-1` | 4px | Icon/text gap, tight metadata |
| `space-2` | 8px | Badge gaps, compact row padding |
| `space-3` | 12px | Control grouping, card internal gaps |
| `space-4` | 16px | Default card padding, field spacing |
| `space-6` | 24px | Section internal separation |
| `space-8` | 32px | Major section separation |
| `space-12` | 48px | Page region separation, rare |

Rules:

- component internals use 4–16px;
- sibling cards use 8–16px;
- a section heading to content uses 12–16px;
- major sections use 24–32px;
- page edges use 16px mobile, 24–32px desktop;
- never add arbitrary 5, 7, 13, 18, or 22px gaps in new work;
- density variants may step down one token, not invent a new scale.

## 7. Component library

### Cards

Canonical card anatomy:

1. optional kicker/status;
2. title;
3. primary value or decision;
4. evidence/body;
5. metadata;
6. optional actions.

Variants:

- **primary:** current priority or selected item; cyan stripe;
- **secondary:** supporting content; neutral border;
- **opportunity:** trade/waiver upside; teal stripe;
- **warning:** caution or temporary pressure; amber stripe;
- **danger:** blocked/invalid/destructive; red stripe;
- **diagnostic:** experimental or data-quality context; indigo stripe;
- **Premium:** entitlement explanation; yellow stripe, never a recommendation card.

Cards use `radius-lg`, Level 0–2 elevation, and 16px padding. Only one card in a
local decision group may be primary. A clickable card must be a semantic button/link
or implement full keyboard behavior, an accessible name, and visible focus.

### Buttons

| Variant | Use |
|---|---|
| Primary | One dominant action in the current region |
| Secondary | Alternative action |
| Tertiary/ghost | Low-priority action, disclosure, navigation |
| Destructive | Irreversible or material removal |
| Premium | Existing upgrade destination only; not generic primary |

Buttons use direct verbs and specific objects: “Open Trade Hub,” not “Continue” when
the destination is known. Minimum height is 44px and minimum touch width is 44px.
Loading preserves label width and announces progress. Icon-only buttons require an
accessible name and 44px target.

### Badges

Badges communicate compact status: Premium, Experimental, Read Only, Current,
Degraded. They do not trigger actions. Use `radius-sm` by default; use a pill only
for very short status text. Keep labels under 18 characters.

### Pills

Pills are selectable compact filters or mutually exclusive board sections. They
must expose radio/tab semantics, selected state, arrow-key behavior where
appropriate, and horizontal overflow handling on mobile. A pill is not a badge.

### Dialogs

- Use for focused detail that benefits from preserving page context.
- Require a visible title, close mechanism, focus trap, Escape behavior, and focus
  restoration.
- Never place essential first-use education only in a dialog.
- One primary action maximum.
- Width: content-based up to 720px; full-screen or bottom-sheet treatment on small
  phones when content cannot reflow.

### Drawers and sheets

- Use for navigation, league/account actions, or supporting detail.
- Do not cover persistent controls without hiding or disabling them.
- Provide heading, close action, focus management, and scroll containment.
- Mobile sheet height must respect dynamic viewport and safe areas.

### Section headers

An optional kicker, required title, and optional one-sentence note. The title
describes the content; the note explains why it matters. Do not add a decorative
icon unless it conveys a labeled semantic state.

### Tables

Use only when comparison across rows and columns is the task.

- Keep the identity column visible where supported.
- Align text left, numbers right, and use tabular numerals.
- Include units in headers.
- Avoid color-only cells.
- Provide an accessible caption or adjacent section description.
- At mobile breakpoints, reduce nonessential columns; if the core task cannot fit,
  convert each row to a canonical compact card.
- Never shrink body text below 12px to preserve columns.

### Lists

Use lists for scan-order content that does not require column comparison. Keep row
height at least 44px when interactive. Put the primary label first, value second,
metadata third. Connected rows use flat edges and 1px separators.

### Empty states

Defined in section 11. Empty states always distinguish expected scarcity from data
or service failure.

### Loading states

- Startup uses the coordinated full-viewport startup shell.
- Page operations use inline status near the content being replaced.
- Use a spinner for uncertain short waits; progress for determinate multi-stage work.
- Do not mount placeholder cards for operations consistently under one second.
- Preserve layout where practical to avoid jumps.
- State what is loading in user language, not function names.

### Error states

- State what failed, impact, and safe next action.
- Preserve already valid data where possible.
- Red is reserved for actual error/invalid/destructive states.
- Never expose tokens, identifiers, stack traces, or raw provider payloads.
- Retry is offered only when retry can change the outcome.

### Success messages

Use for completed state changes, not static healthy status. Keep them concise and
non-blocking. Do not make users dismiss routine confirmations.

### Progress indicators

Use determinate progress only when the application knows meaningful total progress.
Provide an accessible label and current value. Do not imply precision from arbitrary
stages.

### Tooltips

Use for brief definitions of unfamiliar labels, never essential instructions or
action requirements. Tooltips must work on focus and hover and must not contain
interactive content.

### Information callouts

Use cyan for neutral guidance, indigo for diagnostic/experimental context, amber for
caution. Anatomy: short title, one concise body, optional single action. Avoid
stacking multiple callouts.

### Premium banners

Premium treatment is defined in section 10. It must be visually distinct from
recommendations and never imply hidden results unless hidden approved results exist.

### Experimental labels

Use the diagnostic/indigo color, explicit “Experimental” text, and a concise scope
or limitation. “Read Only” is separate and should appear when relevant. Experimental
is not synonymous with Premium.

### Navigation

- Current destination is unambiguous in text and state.
- Group by user task, not module ownership.
- Desktop and mobile use the same labels and route order.
- One navigation action produces one normal rerun.
- Preserve direct links, back/forward, refresh, and query-route contracts.
- Do not place destructive or data-refresh actions among destination links.

### Search

- Label the searchable domain.
- Use a visible label or persistent accessible name, not placeholder alone.
- Preserve query when opening and returning from detail where practical.
- Show count and clear action when filters are active.
- Empty search results differ from empty source data.

### Filters

- Default state should produce useful results.
- Use pills for short exclusive sets, select controls for longer exclusive sets,
  checkboxes for independent conditions.
- Provide a clear-all action when more than two filters can be active.
- Filter changes must not silently alter valuation or league context.

## 8. Standard page template

Every primary page maps to this order unless an exception is documented:

1. **Application shell:** navigation, league/account context.
2. **Page header:** page title, one-sentence subtitle, context metadata.
3. **Primary action region:** one primary action; secondary actions adjacent but
   visually subordinate.
4. **Summary:** two to four summary cards or metrics.
5. **Primary content:** the page's core decision or comparison.
6. **Supporting content:** evidence, alternatives, and detail.
7. **Diagnostics / raw data:** collapsed or clearly secondary.
8. **Help / feedback:** contextual help, limitations, or feedback entry.

### Exceptions

- Startup shell replaces the page template until `PAGE_READY`.
- Launch/import precedes a valid application shell.
- Player Detail may use identity/profile before actions.
- Live Draft may prioritize current pick status above page summary.
- Legal pages use document structure, not decision cards.

Every exception must preserve semantic headings, navigation, accessibility, and
mobile order.

## 9. Data visualization guidance

### General rules

- State the question the visualization answers.
- Prefer exact labels and values over decorative charts.
- Use consistent scales when comparing the same metric.
- Show units, timeframe, source/freshness where relevant.
- Do not use 3D, gradients as quantitative encodings, or unlabeled gauges.
- Color supports position or direction; it does not replace labels.

### Trust

Trust is an evidence-quality boundary, not a score of expected success.

- `Pass`: success color plus “Verified/Pass” text where user-facing.
- `Degraded`: warning color plus plain-language evidence limitation.
- `Blocked`: danger color and reason; blocked recommendations are not presented as
  actionable cards.
- Never show an unlabeled red/green Trust dot.
- Trust must remain visually separate from confidence and fairness.

### Values

- Use tabular numerals and consistent compact formatting.
- Current value and change use separate labels.
- A value is neutral unless compared to a baseline.
- Avoid implying false precision; round according to the existing value contract.

### Trends and ranking movement

- Up/down arrows always include signed change and comparison period.
- Green/red is allowed only when direction has an unambiguous beneficial meaning.
- For rankings, a lower numeric rank can be improvement; label “Up 3” rather than
  relying on `+3`.
- New/unranked is diagnostic, not zero.

### Confidence

- Use named bands already supported by the recommendation contract.
- Pair the band with a reason.
- Do not convert confidence to arbitrary percentages.
- Confidence is not Trust, fairness, or expected win probability.

### Tiers

Tier colors are ordinal labels, not semantic success states:

- Elite: `color-action` / yellow;
- strong/star: primary cyan or silver;
- starter/core: opportunity teal;
- depth: neutral silver;
- uncertain/unclassified: diagnostic indigo;
- unavailable/ineligible: muted or danger according to reason.

Always render the tier name. Do not reuse tier color for buttons.

### Positive and negative changes

The metric definition determines direction. Show:

- label;
- current value;
- signed or verbal change;
- period/baseline.

Use opportunity teal for beneficial movement, danger red for clearly harmful
movement, and neutral silver where direction is contextual.

### Progress bars

- Use only for meaningful bounded progress.
- Label numerator/denominator or percentage.
- Do not use progress bars for rankings, confidence, or fairness unless the domain
  has a real bounded scale and the label explains it.

## 10. Premium language and presentation

### Visual contract

- Premium uses `color-premium` yellow for entitlement badges and upgrade borders.
- Cyan remains the normal interaction color, including on Premium pages.
- Premium content itself uses ordinary component semantics; it should not turn every
  unlocked card yellow.
- Premium badges say “Premium,” not vague lock icons.

### Upgrade card

An upgrade card:

- is separate from recommendation cards;
- names the capability and user outcome;
- has one existing supported upgrade action;
- does not reveal hidden recommendation details;
- does not state a hidden count unless known;
- does not appear for Premium users;
- does not imply hidden results when none exist.

### Locked features

Explain what remains usable now and what additional depth Premium unlocks. Never
disable basic navigation to advertise Premium. Locking must follow canonical
entitlement logic.

### Premium copy

Use “more depth,” “expanded board,” or “additional intelligence.” Do not claim:

- greater accuracy;
- guaranteed recommendations;
- guaranteed wins;
- exclusive valuations unless product policy explicitly establishes them.

### Experimental Premium features

Render both labels when applicable: `Premium` describes access; `Experimental`
describes maturity. Neither label substitutes for the other.

## 11. Empty and system-state patterns

Every state uses: **title → reason → next step**, with an optional supporting note.

| State | Meaning | Tone | Required next step |
|---|---|---|---|
| No data | Source has no usable data | Neutral/diagnostic | Explain source or refresh path |
| No league | User has not selected context | Information | Import or choose league |
| No match | Search/filter excludes all items | Neutral | Clear or adjust filters |
| No recommendations | Generation/Trust produced no valid idea | Neutral, trustworthy | Explain scarcity and suggest another workflow |
| Gated | Approved content exists but access limits it | Premium | Existing upgrade destination |
| Loading | Work is in progress | Information | Usually none; optional cancel only if supported |
| Error | Operation failed | Danger | Retry or safe alternative |
| Offline/degraded | Service unavailable; cached/partial data shown | Warning | Explain freshness and refresh option |
| Success | User action completed | Success | Optional logical next action |

Rules:

- never use “No data” for a network error;
- never use an upgrade card for genuine recommendation scarcity;
- never expose an empty blank panel;
- preserve valid partial results during degraded service;
- retry controls must be idempotent or clearly describe consequences.

## 12. Accessibility

### Contrast

- Normal text: WCAG AA 4.5:1 minimum.
- Large text: 3:1 minimum.
- UI components, focus, and meaningful graphical objects: 3:1 minimum.
- Muted and disabled states still meet the applicable requirement.
- Semantic palettes require automated and rendered-state checks.

### Keyboard and focus

- Every action is reachable and operable by keyboard.
- Visual order matches focus order.
- Focus ring is never removed without an equivalent.
- Dialogs and drawers trap focus and restore it to the trigger.
- Custom cards support Enter and Space only when they semantically act as buttons.
- Escape closes dismissible overlays.

### ARIA and semantics

- Prefer native elements before ARIA.
- One page-level heading; ordered section headings.
- Regions, navigation, dialogs, tables, progress, and status messages are labeled.
- Decorative glyphs use `aria-hidden`.
- Dynamic status uses restrained `aria-live="polite"`; errors may use assertive
  announcement only when immediate intervention is required.
- Accessible names state destination or object, not generic “View.”

### Touch and zoom

- Minimum target: 44×44 CSS pixels.
- Minimum separation between independent compact targets: 8px.
- Inputs use 16px type on mobile.
- Do not disable pinch zoom.
- Content reflows at 320 CSS pixels and 200% zoom.

### Motion

- Honor reduced motion.
- No essential information depends on animation.
- Avoid auto-advancing content, parallax, pulsing urgency, or delayed entrance
  animations.

## 13. Mobile responsiveness

### Breakpoints

Breakpoints describe layout behavior, not device brands:

| Range | Name | Expected behavior |
|---|---|---|
| `0–379px` | Compact phone | Single column, shortest metadata, no optional columns |
| `380–699px` | Phone | Single column, compact cards |
| `700–899px` | Tablet / mobile shell | Single or two-column summaries; mobile navigation |
| `900–1199px` | Compact desktop | Desktop navigation; constrained grids |
| `1200px+` | Wide desktop | Full content width, bounded at application maximum |

The existing `900px` mobile-shell boundary remains the principal contract until a
future migration proves otherwise.

### Card stacking

- Primary content comes first in DOM and visual order.
- Two- or three-column desktop cards stack to one column unless each card remains at
  least 280px wide.
- Do not reorder evidence ahead of the decision merely to fill a grid.
- Preserve 12–16px card spacing.

### Table collapse

1. Remove optional metadata columns.
2. Keep identity plus the two values required for the task.
3. If horizontal comparison no longer works, use compact row cards.
4. Raw full tables may remain in an explicitly labeled detail expander.

Horizontal page scrolling is never acceptable. A table-specific scroll container is
acceptable when comparison requires it and keyboard access is preserved.

### Navigation

- Mobile receives the same core destinations and labels.
- The destination sheet must not overlap feedback, dialogs, or safe areas.
- Current destination remains visible.
- No desktop-only route may be required to complete a core task.

## 14. Future application shell guidance

This section defines principles, not an implementation.

### Shell responsibilities

- Persistent product identity.
- Current league and team context.
- Primary destination navigation.
- Account and entitlement entry.
- League switching and data refresh access.
- Route restoration and direct-link compatibility.

### League switcher

- Show current league and team before the action.
- Separate switching from refresh and import.
- Mark last/default/current leagues explicitly.
- Support long names and multiple seasons.
- Never expose raw identifiers.

### Account entry

- Show Guest, Free, or Premium state in text.
- Keep login/logout, saved leagues, billing, and account details in one discoverable
  entry without mixing them into page navigation.
- Authentication restoration remains owned by Startup Coordinator.

### Navigation

- Group by user task: Home, Roster, League, Transactions, Draft, Intelligence,
  Support.
- Core destinations lead; experimental destinations are subordinate.
- Desktop and mobile share the registry.
- Navigation must not execute data refresh or mutate business state.

### Header behavior

- Page identity and league identity remain distinct.
- Avoid repeating the same title in hero, topbar, and page shell.
- Preserve a stable shell during reruns.
- On scroll, retain only context necessary to avoid disorientation.
- Do not prescribe sticky behavior until browser measurements show value.

## 15. Migration strategy

Migration is incremental and behavior-preserving.

### Phase rules

1. Inventory a component family before editing it.
2. Add visual-regression baselines for desktop and mobile.
3. Map old selectors/tokens to canonical semantic roles.
4. Migrate one shared component family.
5. Verify accessibility, behavior, and page-specific exceptions.
6. Remove obsolete selectors only after every consumer is migrated.

### Compatibility

- Existing selectors may temporarily alias canonical tokens.
- Do not globally replace colors or radii without rendered verification.
- Do not migrate business logic with visual work.
- Do not rewrite page layout merely to adopt tokens.
- Preserve Streamlit public APIs, route behavior, cache boundaries, and session state.

### Definition of done for a migrated component

- uses canonical semantic tokens;
- has documented variants and states;
- works at 320, 390, 768, 1024, and 1440px;
- passes keyboard, focus, zoom, contrast, and reduced-motion checks;
- has empty, loading, error, and disabled states where applicable;
- has no page-specific hex, spacing, or radius overrides;
- retains behavior and content contracts;
- includes visual-regression evidence.

### Governance

- Changes to canonical tokens require a focused design-system decision record.
- New component variants need a cross-page use case, not one page preference.
- Exceptions must document reason, owner, and removal condition.
- Design-system version changes are recorded at the top of this document.

## 16. Recommended implementation order

1. **Create a token alias layer** for the canonical foundation, semantic, spacing,
   type, radius, elevation, and focus tokens without changing rendered output.
2. **Standardize section headers and page shells**, establishing heading hierarchy
   and page-template compliance.
3. **Standardize buttons, badges, pills, and focus states**, because these affect
   every interaction and accessibility.
4. **Consolidate system states**: no data, no match, no recommendation, gated,
   loading, degraded, error, and success.
5. **Migrate shared summary and intelligence cards**, one family at a time.
6. **Migrate dialogs, sheets, search, and filters** with keyboard/focus tests.
7. **Migrate Premium and Experimental presentation** without entitlement changes.
8. **Migrate task-critical mobile tables to compact cards** only where comparison
   remains usable.
9. **Evaluate the future application shell** after shared components converge.
10. **Remove obsolete CSS generations** only after selector usage and screenshot
    baselines prove safe removal.

The first implementation should be the token alias layer. It offers a stable
vocabulary and low rollback risk while producing no intended visual change.

## 17. Explicit exclusions

This specification does not authorize:

- page redesign;
- component migration;
- new navigation or shell implementation;
- Startup changes;
- Trade Hub changes;
- Trust changes;
- Premium entitlement or pricing changes;
- business-logic changes;
- global CSS replacement;
- new fonts, external assets, or hosting;
- visual changes without controlled desktop/mobile validation.

Future implementation work must be scoped, tested, and reviewed independently.
