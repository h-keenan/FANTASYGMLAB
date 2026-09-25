# FantasyGM Lab — UI Hierarchy & Information Architecture Directive

> Sent by coridian_ via Discord, 2026-09-25. Governs all future UI redesign work unless a
> page-specific prompt explicitly overrides part of it. Follow `UI_MAGNA_CARTA.md` for the global
> visual system; this document governs information hierarchy, page composition, feature
> preservation, density, and shared UI patterns. Read alongside `UI_V2_ARCHITECTURE_RESET.md`,
> which this directive closely reinforces and sharpens.

## 1. Primary rule: design around the user's decision

Do not organize a screen based primarily on existing component order, backend object structure,
historical layout, or what is easiest to preserve from the current UI. Instead, begin every screen
by asking: **what is the most important question the user came to this page to answer?** Build the
hierarchy around that answer.

General hierarchy: primary decision/insight → supporting context → actions → detailed information
→ secondary/reference information. The most important content should be understandable within
seconds.

## 2. Existing UI is not the required skeleton

Existing screens are authoritative for functionality, available data, business logic,
calculations, interactions, navigation, and states. They are **not** authoritative for
presentation hierarchy. You may substantially change section order, layout, grouping, card
structure, density, which items share a container, which information appears above the fold,
sticky behavior, and how supporting information is exposed. Do not simply put nicer styling around
the old layout.

## 3. Concept images define hierarchy

When a concept image is provided, treat it as the primary target for composition, hierarchy,
relative sizing, density, grouping, section order, and spacing — not merely a color/style
reference. If the concept materially reorganizes the screen, implement that reorganization.
However, the concept is not a source of truth for data or complete functionality.

## 4. Feature parity is mandatory

A redesign is not permission to remove features. Before implementation, inventory every existing
user-facing capability on the screen — buttons, dropdowns, filters, sort controls, tabs, chips,
badges, favorite/star actions, overflow menus, share actions, compare actions, save/target actions,
contextual help, "About this screen", tooltips, expandable information, injury/status information,
unread/new indicators, breakdown/detail links, alternate views, league controls, strategy/mode
controls, secondary metadata. Every meaningful existing capability must remain directly visible,
move to a better location, be condensed into an appropriate shared control, or move into contextual
overflow/details — but must not silently disappear. If something truly cannot fit the new design,
call it out before removing it.

## 5. Before coding, produce a feature map

For each redesigned screen, first internally map `Existing feature/data → V2 location`. Example:
Favorite action → global header; About this screen → compact contextual help; Player comparison →
action row; Awards → horizontal achievement strip; Detailed analytics → lower-page grouped
analytics sections. Use that map while rebuilding the page.

## 6. One dominant module per screen

Every page should have a clear visual focal point: League Overview → Today's Game Plan; Next Move →
highest-priority action; Waivers → personalized Priority Adds; Trade Hub → actionable trade
recommendations; Matchup → team comparison + recommended lineup; My Team → roster health/franchise
snapshot; Player Detail → player identity + value + GM recommendation. Do not make six sections
visually equally important.

## 7. Information above the fold

The first viewport should deliver meaningful value. Avoid using most of the top screen for
branding, oversized headers, empty padding, decorative cards, or low-priority metadata. A user
should generally see page identity, the primary insight/action, and at least part of the next
useful module within the initial viewport.

## 8. Reduce card-stack UI

Avoid `card → card → card → card → card` when related information can be grouped. Prefer grouped
surfaces, rows with dividers, compact metric clusters, horizontal strips, insight rows, segmented
controls, and shared list containers. Use an independent card only when the content represents a
genuinely independent object or decision.

## 9. Lists are global design patterns

Any repeated list design should be considered for app-wide reuse: players, teams, rankings, roster
slots, waiver targets, trade assets, alerts, draft picks, navigation items, activity/history rows.
Do not redesign a player list only inside one page if the same conceptual row appears elsewhere.
Prefer shared primitives + variants, e.g. `PlayerRow variant="roster"|"matchup"|"ranking"|"waiver"`
— variants may expose different supporting data while preserving identity hierarchy, portrait
treatment, typography, spacing, badge language, status treatment, and row density. If a page
redesign improves a list pattern, promote the improvement into the shared component system.

## 10. Do the same for other repeated patterns

Shared patterns should also exist for: recommendations, trade assets, draft-pick assets,
navigation rows, section headers, segmented controls, buttons, team identity, action tiles,
metrics, status/alert rows. Do not let each page independently reinvent them.

## 11. Player information hierarchy

Wherever a player appears, normally prioritize: player name/portrait → position + NFL team →
meaningful tier/status → context specific to the screen → supporting metrics. Do not let OVR,
value, badge collections, or status chips visually overpower the player's identity unless that
screen specifically exists to rank/value players.

## 12. Recommendations should be stronger than raw data

FantasyGM Lab is a GM assistant, not merely a database. When the model has an actionable
conclusion, prioritize it over raw metrics. Better: a bold headline ("Starter At Risk — Usage has
fallen for three weeks") followed by detailed usage data. Worse: five metric cards followed by a
tiny sentence saying "Starter At Risk." Use raw data to support the recommendation, not bury it.

## 13. Detail should be progressive

Not everything needs to be visible simultaneously. Use progressive disclosure for secondary
information: expandable details, sheets, Full Breakdown, View All, secondary tabs. Keep important
information visible; keep deep/reference information accessible without overwhelming the primary
view.

## 14. Action hierarchy

Avoid multiple equally dominant buttons. Every screen/module should generally have one primary
action, secondary actions, and tertiary/detail actions. Example (waiver recommendation): primary =
act/add where supported; secondary = Full Breakdown; supporting = player detail. Do not make every
action a giant cyan-outline button.

## 15. Remove empty visual weight

Avoid containers that are much taller than the information they contain: one metric inside a giant
card, one award inside a huge panel, one line of bio data inside an entire section, oversized
navigation tiles, massive padding around simple rows. Compact information intelligently.

## 16. Mobile density target

The UI should be information-rich but comfortable. On a modern iPhone, a user should usually see
multiple meaningful pieces of content at once. Increase density through better grouping, shorter
copy, row layouts, internal dividers, and sensible typography — not by shrinking text.

## 17. Header must not dominate

The global header is app chrome, not page content. Keep it consistent and compact. Do not allow
title duplication, oversized brand treatment, overlapping sticky controls, or status-bar
collisions. Respect safe areas structurally.

## 18. GM orb is canonical

Keep the floating GM orb. There is no generic persistent footer or bottom navigation. Page layouts
must accommodate the GM orb without allowing it to cover important interactions. Do not replace it
because a reference concept contains conventional bottom navigation.

## 19. Page-specific hierarchy examples

- **League Overview**: Today's Game Plan → league context → core actions → My Team snapshot →
  recent recap/activity.
- **Player Detail**: player identity + value → GM/roster recommendation → critical status/news →
  primary actions → snapshot → tabs → position-aware analytics → awards/bio/reference.
- **My Team**: franchise/team health → strengths/weaknesses → starters → bench/depth → detailed
  analysis.
- **Waivers**: search/filter → personalized Priority Adds → FAAB/acquisition guidance → Best
  Available market snapshot → full player pool.
- **Trade Hub**: recommendation/filter context → send↔receive assets → value/fairness → why it
  works → confidence/realism → additional trades.
- **Matchup**: matchup comparison → matchup verdict → suggested lineup → opponent lineup →
  supporting analysis.
- **Next Move**: Top Priority → urgent risks → opportunities → supporting league context.

## 20. Build new presentation when necessary

If the existing component architecture makes the new hierarchy difficult, do not contort the old
component until it approximately resembles the concept. Instead: retain existing hooks/data/
controllers, create a new presentation component, connect the existing logic, migrate the route to
the new presentation, and remove the obsolete legacy presentation once parity is verified. The
objective is new UI using proven logic, not old UI with increasingly complicated CSS.

## 21. Visual acceptance test

After implementation, compare the result to the supplied concept image. Evaluate: does the first
viewport have the same basic hierarchy; is the dominant module similarly dominant; are section
proportions reasonably similar; is information density similar; is there excessive whitespace; did
legacy giant cards survive unnecessarily; did section order actually change where requested? If the
implementation still resembles the old screenshot substantially more than the concept, the redesign
is not complete.

## 22. Feature parity check

Before finishing, provide a `Feature Parity: Old feature → New location` table for all meaningful
interactions/features on the page (e.g. Favorite → global header; About this screen → contextual
help; Full Breakdown → recommendation secondary action; Compare → player action row). This ensures
small but valuable product features are not accidentally lost.

## 23. Shared component report

After every redesign, identify: shared components reused; shared components created; existing
components generalized; duplicated legacy components that can now be removed; other screens that
should adopt the improved pattern. If a design improvement has app-wide applicability, do not leave
it trapped inside one page.

## 24. Do not change business logic

Unless specifically requested, do not alter valuation algorithms, recommendation algorithms, FAAB
calculations, lineup generation, trade logic, rankings, league logic, API behavior, subscriptions,
or authentication. UI hierarchy work should consume existing data and logic.

## Final principle

**Preserve the product. Replace the presentation.** Do not remove useful features. Do not preserve
bad layouts. Make every screen communicate: what matters? Why does it matter? What can I do about
it? Everything else should support those three questions. FantasyGM Lab should feel like one
cohesive mobile GM command system, not a collection of legacy pages with updated colors.
