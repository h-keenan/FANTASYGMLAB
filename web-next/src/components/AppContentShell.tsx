"use client";

import { Suspense, type ReactNode } from "react";
import { usePathname } from "next/navigation";

import { useAuth } from "@/context/AuthContext";
import { EspnUnavailableState } from "@/components/EspnUnavailableState";
import { espnUnavailableLeagueId } from "@/lib/leaguePlatform";

/**
 * coridian_, 2026-10-19, screenshot: "still weird clipping and scaling on
 * the desktop welcome page" — the signed-out landing page rendered with a
 * large empty gap on the left instead of being centered.
 *
 * Root cause: layout.tsx's content wrapper applied `md:pl-60` (the space
 * reserved for DesktopSidebar) unconditionally on every page, but
 * DesktopSidebar itself already returns null for a signed-out visitor
 * (`if (!session) return null`, see that component). The padding and the
 * sidebar's own visibility were two independent checks that could drift —
 * exactly the "two sources of truth" bug class this fixes by reading the
 * same `session` check once, here, so the content can never be padded for
 * a sidebar that isn't actually there.
 *
 * Also the one place ESPN leagues are kept off pages they can't feed yet
 * (lib/leaguePlatform.ts): every league page renders through here, so one
 * check covers all of them instead of a copy per page.
 */
export function AppContentShell({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const pathname = usePathname();
  const espnLeagueId = espnUnavailableLeagueId(pathname);
  return (
    <div className={`flex flex-col flex-1 ${session ? "md:pl-60 pb-12 md:pb-0" : ""}`}>
      {espnLeagueId ? (
        // EspnUnavailableState reads ?name= (useSearchParams), which Next
        // requires to sit under a Suspense boundary.
        <Suspense fallback={null}>
          <EspnUnavailableState leagueId={espnLeagueId} />
        </Suspense>
      ) : (
        children
      )}
    </div>
  );
}
