# DynastyGM Interface Reimagining

PR #75 changes DynastyGM’s presentation into one front-office command center. It does not alter football data, calculations, recommendations, navigation, or application state.

## Visual architecture

The final shared CSS layer in `modules/interface_reimagining_styles.py` sits above the existing semantic tokens and canonical components. It changes composition without creating new page-specific component systems:

- the application workspace becomes an operations masthead with page mission, active-league context, and compact telemetry;
- page introductions become operational briefs with stable page-specific CSS namespaces;
- Dashboard reads as an executive decision briefing;
- Trade Hub reads as a negotiation workspace;
- Waivers reads as a scouting board;
- Explorer reads as an asset database;
- League Intelligence reads as an overnight briefing.

All styling references the existing semantic token layer. The layer is loaded once with the application stylesheet and contains no football logic or runtime state.

## Interaction and accessibility

The redesign preserves native Streamlit controls, existing routes, canonical disclosures, modals, and Football Asset behavior. Focus rings, semantic headings, touch-target minimums, overflow handling, responsive collapse, and reduced-motion behavior remain explicit contracts.

Desktop layouts use denser multi-column briefing structures. At mobile widths they collapse to a single readable flow, with actions and controls retaining at least the canonical minimum touch target.

## Behavior boundary

The following remain unchanged:

- player and pick values, rankings, Dynasty Score, and archetypes;
- Dashboard calculations and advice;
- Trade Hub generation, ordering, scoring, Trust enforcement, and entitlement;
- Waivers generation, opportunity calculations, ordering, and filtering;
- Player Quick View and Football Asset interactions;
- League Intelligence inputs and recommendations;
- authentication, Startup Coordinator, caching, routing, and navigation.

## Maintenance

Future visual changes should extend semantic tokens or canonical components first. The final overlay is reserved for cross-application composition and room-level hierarchy—not football behavior or isolated page widgets.
