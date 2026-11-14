/**
 * The desktop sidebar on /sample-league (docs/audits/2026-11-live-site-qa.md D1 + the 2026-11-14 desktop pass): the
 * sample has no league, so it must not offer pages that need one. It shows the sample's own views (in-page tabs, driven
 * through a window event so the sidebar and the page stay decoupled), the one way to connect a real league, and only
 * the destinations that work without a league. Founder items stay for the founder. Web only (the app has no sidebar).
 */
import type { NavDestination } from "@/lib/navDestinations";

export const SAMPLE_PATH = "/sample-league";
/** Sidebar -> page: switch the sample view (detail: SampleTab). */
export const SAMPLE_SELECT_EVENT = "fgl:sample-select";
/** Page -> sidebar: the sample view that is showing (detail: SampleTab), so the sidebar can mark it. */
export const SAMPLE_ACTIVE_EVENT = "fgl:sample-active";

/** Paths that work with no league connected (everything else under General/Account needs saved leagues). */
const DEMO_USABLE_PATHS = new Set(["/gm-game", "/news", "/community", "/premium", "/account"]);

export function isSamplePath(pathname: string | null | undefined): boolean {
  return pathname === SAMPLE_PATH || pathname === `${SAMPLE_PATH}/`;
}

/** Keep only the destinations a visitor with no league can actually use. */
export function demoUsableDestinations(destinations: readonly NavDestination[]): NavDestination[] {
  return destinations.filter((destination) => DEMO_USABLE_PATHS.has(destination.path.split(/[?#]/)[0]));
}
