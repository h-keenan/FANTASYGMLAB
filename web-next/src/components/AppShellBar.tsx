"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import { NavDestinationGlyph } from "@/components/NavDestinationGlyph";
import { NavProMarker } from "@/components/NavProMarker";
import { BottomTabBar } from "@/components/ui/BottomTabBar";
import { Sheet } from "@/components/ui/Sheet";
import { useAuth } from "@/context/AuthContext";
import { useDisplayPreferences } from "@/context/DisplayPreferencesContext";
import { FOUNDER_DESTINATION, isFounderSession, useNavDestinations, type NavDestination } from "@/lib/navDestinations";
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
 * Fantasy Sim / News / More. More opens the full menu, grouped, from the one
 * shared catalog (lib/navCatalog.ts via useNavDestinations): same groups,
 * glyphs and Pro markers as the orb and the desktop sidebar.
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
  const tabs = shellTabs({ leagueId, leagueName });
  const active = shellActiveTab(pathname, Boolean(leagueId));
  const [moreOpen, setMoreOpen] = useState(false);
  const pill = useSyncExternalStore(subscribePill, getPillState, getServerPillState);
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
  return (
    <>
      <div className="bottom-stack md:hidden" data-bare data-testid="shell-bottom-stack">
        <div id={SHELL_ACTION_SLOT_ID} className="shell-action-slot empty:hidden" />
        <BottomTabBar
          ariaLabel={leagueId ? "League sections" : "Main sections"}
          tabs={tabs}
          active={active}
          testId="shell-tab-bar"
          // A page registers its own context (counts, primary); until it does, the route alone gives the family tabs, so nothing flashes.
          context={pill.ctx ?? routeFamilyPillContext(pathname, leagueId, leagueName)}
          onSelect={(key) => {
            if (key === "more") setMoreOpen(true);
          }}
        />
      </div>
      <ShellMoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} leagueId={leagueId} leagueName={leagueName} />
    </>
  );
}

function ShellMoreSheet({ open, onClose, leagueId, leagueName }: { open: boolean; onClose: () => void; leagueId: string | null; leagueName: string }) {
  const { session } = useAuth();
  const { collegeInterest } = useDisplayPreferences();
  const { coreLeagueDestinations, gmToolsDestinations, generalDestinations, accountDestinations } = useNavDestinations(leagueId, leagueName, collegeInterest);
  const showPro = useIsPro() === false;
  const founder = isFounderSession(session);
  const groups: { title: string; rows: NavDestination[] }[] = [
    ...(leagueId ? [{ title: "League", rows: coreLeagueDestinations }, { title: "GM tools", rows: gmToolsDestinations }] : []),
    { title: "General", rows: generalDestinations },
    { title: "Account", rows: [...accountDestinations, ...(founder ? [FOUNDER_DESTINATION] : [])] },
  ];
  return (
    <Sheet open={open} onClose={onClose} title="More" description={leagueId ? leagueName : "Everything in FantasyDesk"}>
      <nav aria-label="All pages" className="flex flex-col gap-4" data-testid="shell-more-menu">
        {groups.map((group) => (
          <section key={group.title} aria-label={group.title} className="flex flex-col">
            <h3 className="px-2 pb-1 text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "0.04em" }}>
              {group.title}
            </h3>
            {group.rows.map((row) => (
              <Link key={row.path} href={row.path} onClick={onClose} className="game-nav-row" data-testid="shell-more-row">
                <span className="shrink-0" style={{ color: row.color }}>
                  <NavDestinationGlyph name={row.glyph} size={22} />
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="flex items-center gap-2 text-sm font-bold">
                    {row.label}
                    {row.pro && showPro ? <NavProMarker /> : null}
                  </span>
                  <span className="truncate text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>{row.subtitle}</span>
                </span>
              </Link>
            ))}
          </section>
        ))}
      </nav>
    </Sheet>
  );
}
