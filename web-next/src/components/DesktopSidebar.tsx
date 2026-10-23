"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";

import { useAuth } from "@/context/AuthContext";
import { NavDestinationGlyph } from "@/components/NavDestinationGlyph";
import { useNavDestinations, type NavDestination } from "@/lib/navDestinations";

/**
 * Desktop-width persistent left nav — coridian_, 2026-10-17: "desktop side
 * menu" (repeated across several messages), and "the explore section with
 * all the pages is redundant with the GM orb and the desktop side menu."
 * GmOrb (the mobile-width floating button + bottom sheet) is hidden at
 * this same `md:` breakpoint, and Dashboard's Explore grid is hidden at it
 * too — this sidebar is the one real desktop nav surface, not an addition
 * alongside the other two. Renders from the exact same destination list
 * GmOrb does (src/lib/navDestinations.ts) so neither surface can drift
 * out of sync with the other about what pages exist.
 */
export function DesktopSidebar() {
  const { session } = useAuth();
  const pathname = usePathname();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  const leagueName = searchParams.get("name") || leagueId || "";
  const { coreLeagueDestinations, gmToolsDestinations, generalDestinations } = useNavDestinations(leagueId, leagueName);

  if (!session) return null;

  return (
    <nav
      className="hidden md:flex md:flex-col md:gap-5 md:overflow-y-auto"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        bottom: 0,
        width: "15rem",
        padding: "1.25rem 1rem",
        background: "var(--color-surface-secondary)",
        borderRight: "var(--border-width-default) solid var(--color-border)",
        zIndex: 30,
      }}
    >
      <Link href="/" className="flex items-center gap-2 px-1">
        <Image src="/brand-mark.png" alt="" width={24} height={24} className="brand-mark-icon" style={{ objectFit: "contain" }} />
      </Link>

      {leagueId ? (
        <SidebarSection label={leagueName || "League"} destinations={coreLeagueDestinations} pathname={pathname} />
      ) : (
        <p className="text-xs px-1" style={{ color: "var(--color-text-muted)" }}>
          Open a league from Home to unlock Players, Waivers, Trade Analyzer, and more.
        </p>
      )}

      {leagueId ? (
        <SidebarSection label="GM Tools" destinations={gmToolsDestinations} pathname={pathname} />
      ) : null}

      <SidebarSection label="General" destinations={generalDestinations} pathname={pathname} />
    </nav>
  );
}

function SidebarSection({
  label,
  destinations,
  pathname,
}: {
  label: string;
  destinations: NavDestination[];
  pathname: string | null;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span
        className="text-xs font-bold uppercase px-1"
        style={{ color: "var(--color-text-secondary)", letterSpacing: "0.04em" }}
      >
        {label}
      </span>
      <div className="flex flex-col">
        {destinations.map((destination) => {
          // Strip the ?name=... query before comparing — pathname never
          // carries it, so an exact-string match would always miss.
          const destinationPath = destination.path.split("?")[0];
          const active = pathname === destinationPath;
          return (
            <Link
              key={destination.path}
              href={destination.path}
              className="flex items-center gap-2.5 px-1 py-2"
              style={{
                background: active ? "var(--color-surface-raised)" : "transparent",
              }}
            >
              <span className="shrink-0" style={{ color: destination.color }}>
                <NavDestinationGlyph name={destination.glyph} size={18} />
              </span>
              <span
                className="text-sm font-bold truncate"
                style={{ color: active ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}
              >
                {destination.label}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
