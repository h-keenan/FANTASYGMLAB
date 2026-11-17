"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";

import { NavSheet } from "@/components/NavSheet";
import { usePathname, useParams } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";

import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse } from "@/lib/analytics";
import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import { pathOwnsPhoneChrome } from "@/lib/bottomNav";
import { useShellNav } from "@/lib/useShellNav";
import { UNNAMED_LEAGUE } from "@/lib/leagueName";

/**
 * The floating GM orb button, bottom-center on phones when the site bottom bar is not showing (mobile's GmOrb.tsx is its twin).
 * It owns only the trigger and the header Search icon's open event; the sheet itself is the one shared navigation sheet,
 * components/NavSheet.tsx (also opened by the bottom bar's More button). Desktop uses DesktopSidebar.
 */
export function GmOrb() {
  const [open, setOpen] = useState(false);
  // The header's search icon opens the sheet straight onto the search field; the orb opens it without focus (components/NavSheet.tsx).
  const [focusSearch, setFocusSearch] = useState(false);
  const closeSheet = useCallback(() => setOpen(false), []);
  useEffect(() => {
    const onOpenSearch = () => {
      setFocusSearch(true);
      setOpen(true);
    };
    window.addEventListener(OPEN_SEARCH_EVENT, onOpenSearch);
    return () => window.removeEventListener(OPEN_SEARCH_EVENT, onOpenSearch);
  }, []);
  const { session } = useAuth();
  const pathname = usePathname();
  const { barVisible: shellBar } = useShellNav();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  const leagueName = searchParams.get("name") || (leagueId ? UNNAMED_LEAGUE : "");

  if (!session) return null;
  // Zach, 2026-10-19: "fix the bottom orb on onboard its covering" — "/"
  // is exclusively the signup/Sleeper-import/paywall flow (an already-
  // onboarded signed-in user is always router.replace'd away from it to
  // their league/Portfolio, never shown it) — a floating launcher to jump
  // elsewhere in the app makes no sense mid-onboarding anyway, and its
  // fixed bottom-center position was landing directly on top of the
  // Paywall's own Subscribe button.
  if (pathname === "/") return null;

  // The game's own bottom bar replaces the floating trigger on phones; the sheet (search, destinations) stays
  // mounted and opens from the game header's search icon.
  // Phase B: with the site bottom bar showing, the orb is retired on phones too (More holds the menu).
  const showTrigger = !pathOwnsPhoneChrome(pathname) && !shellBar;

  return (
    <>
      {showTrigger ? (
      <>
      {/* The orb lives in a zero-height `position: sticky; bottom: 0` rail at
          the end of <body>, NOT `position: fixed`. iOS Safari anchors fixed
          elements to the layout viewport, which drifts from the visible one
          (URL/bottom bar collapse, keyboard dismissal, rubber-banding) and
          left the orb floating mid-screen (owner reports, 2026-11-11/12).
          Sticky elements are positioned by the scroller itself, so they stay
          glued to the visible bottom edge with no JS. #1791 tried to chase
          the drift from window.visualViewport; that was removed because it
          could disagree with the sticky/fixed elements it sat next to. The
          rail's parent (body) has no overflow/transform, which sticky needs. */}
      <div className="bottom-rail md:hidden">
      <button
        type="button"
        onClick={() => {
          setFocusSearch(false);
          setOpen(true);
          trackFeatureUse("gm_orb_opened", { leagueId: leagueId || undefined, dedupe: false });
        }}
        aria-label="Open GM menu"
        // coridian_, 2026-10-18: "Gm orb is still too high" — bottom-6
        // (24px) left too much empty space below it; bottom-3 (12px) sits
        // closer to the true bottom edge.
        className="absolute left-1/2 flex items-center justify-center"
        style={{
          // Bottom-center of the sticky rail above; clears the iOS home
          // indicator via the safe-area inset.
          bottom: "max(12px, env(safe-area-inset-bottom, 0px))",
          transform: "translateX(-50%)",
          width: "3.25rem",
          height: "3.25rem",
          borderRadius: "50%",
          background: "var(--color-bg)",
          border: "1.5px solid var(--color-accent)",
          boxShadow: "var(--shadow-card)",
          zIndex: 40,
        }}
      >
        {/* The actual brand mark, not a plain "GM" text label — mobile's own
            GmOrb renders this same mark (coridian_'s brand-continuity ask,
            2026-10-17: the floating nav button is one of the most-seen
            elements on both platforms, so it should actually be the brand,
            not a placeholder). */}
        <span className="flex flex-col items-center" style={{ gap: "1px" }}>
          <Image src="/brand-mark.png" alt="" width={22} height={22} className="brand-mark-icon" style={{ objectFit: "contain" }} />
          {/* The orb was a bare logo: nothing said it opens the nav. The
              visible "GM" matches the aria-label ("Open GM menu"). */}
          <span aria-hidden="true" className="font-extrabold uppercase" style={{ fontSize: "0.625rem", lineHeight: 1, letterSpacing: "0.06em", color: "var(--color-accent)" }}>
            GM
          </span>
        </span>
      </button>
      </div>
      </>
      ) : null}

      <NavSheet open={open} onClose={closeSheet} leagueId={leagueId} leagueName={leagueName} focusSearch={focusSearch} />
    </>
  );
}
