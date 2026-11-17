/**
 * The footer orb's menu affordance (first-time-user audit F1), shared by the web PillOrb and the app GmOrb.
 * Pure constants and the seen-once key; byte-identical in both trees (lib-twins check).
 *
 * - The persistent cue is a small "menu" glyph on the orb's rim (a logo alone does not read as a menu).
 * - The one-time coachmark names what the orb opens. It reuses the `fd-help-seen:` seen-once storage prefix
 *   that BeginnerHelp uses, so "seen" is one convention everywhere.
 */
export const ORB_COACHMARK_TEXT = "Your GM menu: tap to jump to Today, Team, Trades, League, More";
export const ORB_COACHMARK_DISMISS = "Got it";
export const ORB_MENU_CUE_LABEL = "Menu";
export const ORB_COACHMARK_SEEN_KEY = "fd-help-seen:orb-menu";
