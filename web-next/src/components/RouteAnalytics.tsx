"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { trackPageView } from "@/lib/analytics";

/**
 * Fires a `page_view` analytics event on every real route change — see
 * lib/analytics.ts's module doc for the bug this closes (web-next never
 * called into modules/launch_analytics.py at all). Rendered once in
 * RootLayout so every page gets this for free, without each page needing
 * its own wiring.
 *
 * A tiny dedicated component (not inlined in RootLayout) so the rest of the
 * shell doesn't need to re-render on every pathname change just for this —
 * same reasoning as Header.tsx's HeaderLeagueControls split. usePathname
 * alone (unlike useSearchParams) doesn't force this subtree dynamic, so no
 * Suspense wrapper is needed here (Header.tsx's own HeaderPageTitle already
 * uses usePathname directly, unwrapped, for the same reason).
 */
export function RouteAnalytics() {
  const pathname = usePathname();

  useEffect(() => {
    trackPageView(pathname || "");
  }, [pathname]);

  return null;
}
