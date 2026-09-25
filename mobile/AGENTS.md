# Expo HAS CHANGED

Read the exact versioned docs at https://docs.expo.dev/versions/v57.0.0/ before writing any code.

# UI work

Before any FantasyGM Lab UI task, read `mobile/UI_MAGNA_CARTA.md` and treat it as the authoritative default design specification. Page-specific prompts and concept images may change composition and information hierarchy, but they do not override canonical global components, semantic colors, navigation architecture, or shared design tokens unless explicitly stated. When a page requires a new reusable pattern, promote it into the shared component/theme system rather than implementing a local duplicate.

Before any *major screen redesign* (not a small fidelity tweak), also read `mobile/UI_V2_ARCHITECTURE_RESET.md`. It governs how aggressively a redesign may restructure a screen (existing layout is not a skeleton to preserve) and requires a feature-parity inventory/checklist before and after implementation — no existing user-facing feature may be silently dropped because a concept image doesn't show it.

Also read `mobile/UI_HIERARCHY_DIRECTIVE.md` before any redesign work. It sharpens the same rules with concrete checks: one dominant module per screen, player identity must outrank OVR/badge chips, one primary action per module (not several equally-weighted buttons), no card-inside-card-inside-card nesting, shared list/row primitives with variants (`PlayerRow variant="roster"|"matchup"|...`) instead of a new row per page, and a required post-redesign Feature Parity table + Shared Component report.
