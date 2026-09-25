# FantasyGM Lab — UI V2 Architecture Reset

> Sent by coridian_ via Discord, 2026-09-25. Supersedes the *implementation strategy* used for redesign
> work up to this point. `UI_MAGNA_CARTA.md` remains the authoritative design-token/component/semantic
> spec — this document changes how aggressively a redesign is allowed to restructure a screen, and adds
> a mandatory feature-parity process. Read both before any major screen redesign.

We are changing the implementation strategy for the FantasyGM Lab UI overhaul.

Previous redesign work has preserved too much of the existing layout and information architecture.
From this point forward, **do not treat the existing page layout as the visual skeleton that must be
retained.**

The existing screens are authoritative for:
- functionality
- business logic
- backend calls
- available data
- navigation
- actions
- loading/error behavior

They are **not** authoritative for presentation or information hierarchy.

## Core rule

For major redesigned screens, prefer:

> existing data/controller logic → new UI V2 presentation

instead of:

> existing UI → incremental CSS/style modifications

Do not keep old wrappers, old card hierarchy, or old section order solely because they already exist.

## 1. Create a UI V2 presentation layer

Establish a clean shared presentation system for the redesigned app. Reuse business logic, hooks,
services, models, state, navigation, and data fetching. But create/refactor presentation components so
the new UI can actually differ structurally from the legacy UI.

Where appropriate:
- extract data/controller logic from old screens
- pass normalized data into new V2 presentation components
- replace the old screen component only after the new layout works

Avoid duplicating backend logic.

## 2. Do not be constrained by old component structure

If an old page currently contains Header / Card / Card / Four Tiles / Row / Row, that does not mean the
new page must preserve that order or those containers. The new design may reorder sections, combine
modules, split modules, replace cards with rows, replace rows with grouped surfaces, change density,
change sticky behavior, change hierarchy, and change which information is visually primary — as long as
real functionality remains intact.

## 3. Concept images are composition targets

When a new concept image is supplied, match overall structure, relative sizing, information hierarchy,
density, spacing, grouping, and visual emphasis. Do not interpret a concept as merely a palette/style
reference. If the concept places a module in a fundamentally different part of the page, implement that
structural change.

## 4. Screenshot acceptance rule

Every major page redesign must be evaluated visually. After implementation, compare the rendered screen
against the supplied concept and explicitly inspect: top 25% of screen, section ordering, relative card
heights, whitespace, visible information per viewport, font hierarchy, component density, alignment. If
the implementation still visually resembles the old screen more than the concept, the redesign is
incomplete.

## 5. Legacy UI should not leak through

Remove/refactor legacy styling patterns when a V2 equivalent exists — giant outlined boxes, repeated
cyan borders, overly tall metric cards, page-specific player rows, legacy shortcut tiles, oversized
empty containers. Do not leave both V1 and V2 patterns active on the same screen.

## 6. Shared V2 components

Build the new app around shared primitives such as: AppHeader, SectionHeader, DashboardHero,
DashboardActionTile, PlayerRow, TeamRow, MetricGroup, MetricItem, InsightRow, RecommendationCard,
StatusChip, SegmentedControl, GMNavigationSheet, LeagueSwitcher. Use variants/configuration where
appropriate. Do not create a separate visual component system per screen.

## 7. Density target

FantasyGM Lab should be information-rich but not crowded. A normal modern iPhone viewport should
generally show several meaningful modules without excessive scrolling. Avoid giant empty card
interiors, 60–100px gaps with no information, individual cards around every row, oversized headings.

## 8. Visual priority

Every page must have one obvious answer to "what matters most here?" That module receives the
strongest hierarchy. Everything else supports it.

## 9. Global UI consistency

Continue following `UI_MAGNA_CARTA.md`. Shared patterns changed during a page redesign must be promoted
to the app-wide shared component system where appropriate. A new player-list structure, action tile,
team row, metric pattern, etc. should not remain local if other screens use the same conceptual
pattern.

## 10. Do not add a footer

FantasyGM Lab does not use a generic persistent bottom navigation. Preserve the canonical floating GM
orb and global navigation-sheet system.

## 11. Implementation strategy for each page

For every major redesign: inspect the old screen; identify data + functionality that must survive;
identify legacy presentation that can be discarded; inspect the concept image; define the new
information hierarchy; build the new presentation; connect existing data/actions; visually compare
against the concept; remove obsolete legacy presentation; run tests/build checks. Do not stop after
step 7.

## Definition of success

If a user familiar with the old app looks at the redesigned screen, they should immediately recognize
the same functionality but see a materially different, more coherent product UI. Small spacing, color
and radius changes do not qualify as a redesign.

## Feature parity — absolute requirement

A visual redesign is **not** permission to remove features. Before changing any major screen, create an
inventory of every existing user-facing feature on that screen, including small or secondary features
such as: buttons, chips, dropdowns, filters, toggles, tooltips, "About this screen", favorite/star
controls, overflow menus, badges, status indicators, expandable details, contextual help, alternate
views, share actions, compare actions, saved-target actions, breakdown links, league/mode controls,
sorting/filtering, unread/new indicators, drill-down navigation, secondary metadata.

**Do not delete, disable, or silently omit any existing user-facing capability merely because it is not
shown in the concept image.** The concept image defines the new visual hierarchy, not the complete
feature inventory. If a feature is visually low-priority, it may be moved, condensed, placed in an
overflow menu, represented by an icon, grouped into a contextual sheet, or repositioned elsewhere in the
redesigned screen — but it must remain accessible unless coridian_ explicitly approves its removal.

### Feature-parity workflow

Before implementation: inspect the current screen; list every existing user-facing interaction and
piece of meaningful information; mark where each one will live in the V2 design; identify anything that
would otherwise be omitted by the concept; preserve it in an appropriate new location.

After implementation, provide a feature parity checklist showing: `Existing feature → V2 location /
behavior`. Any feature that cannot be preserved must be called out explicitly before removal. Do not
make that decision silently.

## Business logic + small features

Preserve not just major business logic, but also the small product touches that make FantasyGM Lab
useful. A cleaner UI should expose those features more intelligently — not strip the app down.
