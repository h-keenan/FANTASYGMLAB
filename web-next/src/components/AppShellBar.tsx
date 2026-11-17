"use client";

import { useParams, usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import { NavSheet } from "@/components/NavSheet";
import { BottomDock } from "@/components/ui/BottomDock";
import { BottomTabBar } from "@/components/ui/BottomTabBar";
import { isSelectionAction, moreBadgeSummary, moreBadgeTotal } from "@/lib/bottomNav";
import { useShellBadges } from "@/lib/shellBadgeStore";
import { useFooterHideOnScroll } from "@/lib/useFooterHideOnScroll";
import { getPillState, getServerPillState, setPillBarPresent, subscribePill } from "@/lib/bottomPillStore";
import { routeFamilyPillContext } from "@/lib/pageFamilyPill";
import { shellActiveTab, shellLeagueContext, shellTabs, SHELL_ACTION_SLOT_ID } from "@/lib/shellNav";
import { useSearchParams } from "@/lib/useSearchParams";
import { useShellNav } from "@/lib/useShellNav";
import { useIsPro } from "@/lib/useIsPro";
import { UNNAMED_LEAGUE } from "@/lib/leagueName";

/**
 * Phase B phone shell: the site-wide bottom bar. League-aware: inside a league
 * Today / Team / Trades / League / More, outside it Home / Portfolio /
 * Fantasy Sim / News / More. More opens the one shared navigation sheet
 * (components/NavSheet.tsx), the same sheet the header Search icon and the GM orb open.
 *
 * Layout: an in-flow `.bottom-stack` (position: sticky; bottom: 0 at the end
 * of the app column, safe-area padding), never position:fixed or JS-placed, so
 * iOS Safari viewport drift cannot float it. Above the tabs is the page-aware
 * action slot (ShellAction). Phones only; behind the shell flag (lib/useShellNav.ts).
 */
export function AppShellBar() {
  const { barVisible } = useShellNav();
  if (!barVisible) return null;
  return <ShellBarInner />;
}

function ShellBarInner() {
  const pathname = usePathname();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const { leagueId, leagueName } = shellLeagueContext(params?.leagueId ? decodeURIComponent(params.leagueId) : null, searchParams, UNNAMED_LEAGUE);
  const moreBadges = useShellBadges();
  const tabs = shellTabs({ leagueId, leagueName }).map((t) => (t.key === "more" ? { ...t, badge: moreBadgeTotal(moreBadges), badgeSummary: moreBadgeSummary(moreBadges) } : t));
  const active = shellActiveTab(pathname, Boolean(leagueId));
  const [moreOpen, setMoreOpen] = useState(false);
  const pill = useSyncExternalStore(subscribePill, getPillState, getServerPillState);
  // Pro markers on paid tabs only for a person known to be on Free (null while loading: no marker rather than a wrong one).
  const showPro = useIsPro() === false;
  // Tell pages the pill is on screen (phones only) so they drop their own page-tab row only then.
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return; // no media queries (tests, very old browsers): the in-page tabs stay
    const mq = window.matchMedia("(max-width: 767px)");
    const sync = () => setPillBarPresent(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => {
      mq.removeEventListener("change", sync);
      setPillBarPresent(false);
    };
  }, []);
  // Hide on scroll down, back on scroll up; a selection (the primary is the submit) keeps the footer in place.
  useFooterHideOnScroll(isSelectionAction(pill.ctx?.primary));
  return (
    <>
      <BottomDock className="md:hidden" testId="shell-bottom-stack">
        <div id={SHELL_ACTION_SLOT_ID} className="shell-action-slot empty:hidden" />
        <BottomTabBar
          ariaLabel={leagueId ? "League sections" : "Main sections"}
          tabs={tabs}
          active={active}
          testId="shell-tab-bar"
          showPro={showPro}
          // A page registers its own context (counts, primary); until it does, the route alone gives the family tabs, so nothing flashes.
          context={pill.ctx ?? routeFamilyPillContext(pathname, leagueId, leagueName)}
          onSelect={(key) => {
            if (key === "more") setMoreOpen(true);
          }}
        />
      </BottomDock>
      <NavSheet open={moreOpen} onClose={() => setMoreOpen(false)} leagueId={leagueId} leagueName={leagueName} />
    </>
  );
}
