"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import { NavDestinationGlyph } from "@/components/NavDestinationGlyph";
import { NavProMarker } from "@/components/NavProMarker";
import { PlayerName } from "@/components/PlayerName";
import { PositionBadge } from "@/components/PositionBadge";
import { SkeletonText } from "@/components/Skeleton";
import { Sheet } from "@/components/ui/Sheet";
import { useAuth } from "@/context/AuthContext";
import { useDisplayPreferences } from "@/context/DisplayPreferencesContext";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { BRAND_NAME } from "@/lib/brand";
import { PLAYER_SEARCH_MAX_RESULTS, PLAYER_SEARCH_MIN_CHARS, useLeaguePlayerSearchState } from "@/lib/leaguePlayerSearch";
import { FOUNDER_DESTINATION, isFounderSession, searchNavDestinations, useNavDestinations, type NavDestination } from "@/lib/navDestinations";
import { NAV_SHEET_NO_LEAGUE_NOTE, NAV_SHEET_TITLE, navSheetGroups, navSheetNoMatch, navSheetSearchCopy } from "@/lib/navSheet";
import { useIsPro } from "@/lib/useIsPro";

/**
 * THE navigation sheet: "Where to go". The bottom bar's More button, the header Search icon and the GM orb all open this one
 * component (never their own list), so the destinations, grouping, search and look cannot differ by which button was tapped.
 * Search opens it with `focusSearch` (the field is focused); More opens it without. Groups and copy: lib/navSheet.ts (twin of
 * the app's GM orb sheet). scripts/check_nav_sheet.mjs fails when a destination list is rendered anywhere else.
 *
 * Built on the shared `Sheet` (dialog role, focus trap, Escape, scroll lock, swipe-down, overlay stack) with its glass variant.
 */
export function NavSheet({
  open,
  onClose,
  leagueId,
  leagueName,
  focusSearch = false,
}: {
  open: boolean;
  onClose: () => void;
  leagueId: string | null;
  leagueName: string;
  focusSearch?: boolean;
}) {
  const { session } = useAuth();
  const { collegeInterest } = useDisplayPreferences();
  const { openPlayer } = usePlayerQuickView();
  const { coreLeagueDestinations, gmToolsDestinations, generalDestinations, accountDestinations } = useNavDestinations(leagueId, leagueName, collegeInterest);
  // Gold "Pro" markers on paid rows, shown only once we know the plan is Free.
  const showPro = useIsPro() === false;
  const founder = isFounderSession(session);
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const copy = navSheetSearchCopy(Boolean(leagueId));
  // Server-side search over the whole league pool (not just the rankings window).
  const playerSearch = useLeaguePlayerSearchState(leagueId ?? "", "Dynasty", query);
  const wantsPlayers = Boolean(leagueId) && normalizedQuery.length >= PLAYER_SEARCH_MIN_CHARS;
  const playerResults = useMemo(() => playerSearch.players.slice(0, PLAYER_SEARCH_MAX_RESULTS), [playerSearch.players]);

  const groups = useMemo(
    () =>
      navSheetGroups<NavDestination>({
        leagueName: leagueId ? leagueName : null,
        core: coreLeagueDestinations,
        tools: gmToolsDestinations,
        general: generalDestinations,
        account: [...accountDestinations, ...(founder ? [FOUNDER_DESTINATION] : [])],
      }),
    [leagueId, leagueName, coreLeagueDestinations, gmToolsDestinations, generalDestinations, accountDestinations, founder],
  );
  const destinationResults = useMemo(
    () => (normalizedQuery ? searchNavDestinations(groups.flatMap((g) => g.rows), normalizedQuery) : []),
    [normalizedQuery, groups],
  );

  const close = () => {
    setQuery("");
    onClose();
  };

  return (
    <Sheet
      open={open}
      onClose={close}
      title={NAV_SHEET_TITLE}
      eyebrow={BRAND_NAME}
      glass
      initialFocusRef={focusSearch ? searchRef : undefined}
      testId="nav-sheet"
    >
      <input
        ref={searchRef}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={copy.placeholder}
        aria-label={copy.label}
        autoComplete="off"
        className="filter-input px-3 py-2 text-sm w-full"
        data-testid="nav-sheet-search"
      />
      <nav aria-label="All pages" className="flex flex-col gap-4" data-testid="nav-sheet-menu">
        {normalizedQuery ? (
          destinationResults.length > 0 || playerResults.length > 0 ? (
            <>
              {destinationResults.length > 0 ? (
                <div className="flex flex-col">
                  {destinationResults.map((destination) => (
                    <NavRow key={destination.path} destination={destination} showPro={showPro} onNavigate={close} />
                  ))}
                </div>
              ) : null}
              {playerResults.length > 0 ? (
                <NavSection label="Players">
                  {playerResults.map((player) => (
                    <button
                      key={player.player_id}
                      type="button"
                      onClick={() => {
                        close();
                        openPlayer({ ...player, leagueId: leagueId ?? undefined, leagueName, sourceLabel: "Search" });
                      }}
                      className="flex items-center gap-3 py-2.5 text-left"
                      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
                    >
                      <PositionBadge position={player.position} />
                      <span className="flex min-w-0 flex-col">
                        <PlayerName name={player.name} className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }} />
                        {player.team ? (
                          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                            {player.team}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  ))}
                </NavSection>
              ) : null}
            </>
          ) : wantsPlayers && playerSearch.pending ? (
            <SkeletonText label="players" lines={2} />
          ) : (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              {navSheetNoMatch(Boolean(leagueId), query)}
            </p>
          )
        ) : (
          <>
            {!leagueId ? (
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                {NAV_SHEET_NO_LEAGUE_NOTE}
              </p>
            ) : null}
            {groups.map((group) => (
              <NavSection key={group.id} label={group.title}>
                {group.rows.map((destination) => (
                  <NavRow key={destination.path} destination={destination} showPro={showPro} onNavigate={close} />
                ))}
              </NavSection>
            ))}
          </>
        )}
      </nav>
    </Sheet>
  );
}

function NavSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section aria-label={label} className="flex flex-col gap-1">
      <h3 className="text-xs font-bold uppercase" style={{ color: "var(--color-text-secondary)", letterSpacing: "0.04em" }}>
        {label}
      </h3>
      <div className="flex flex-col">{children}</div>
    </section>
  );
}

function NavRow({ destination, showPro, onNavigate }: { destination: NavDestination; showPro: boolean; onNavigate: () => void }) {
  return (
    <Link
      href={destination.path}
      onClick={onNavigate}
      className="flex items-center gap-3 py-2.5"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
      data-testid="nav-sheet-row"
    >
      <span className="shrink-0" style={{ color: destination.color }}>
        <NavDestinationGlyph name={destination.glyph} size={20} />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
            {destination.label}
          </span>
          {showPro && destination.pro ? <NavProMarker /> : null}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {destination.subtitle}
        </span>
      </span>
    </Link>
  );
}
