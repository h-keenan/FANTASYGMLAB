"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { useDisplayPreferences } from "@/context/DisplayPreferencesContext";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { trackFeatureUse } from "@/lib/analytics";
import { BRAND_NAME } from "@/lib/brand";
import { NavDestinationGlyph } from "@/components/NavDestinationGlyph";
import { NavProMarker } from "@/components/NavProMarker";
import { PositionBadge } from "@/components/PositionBadge";
import { FOUNDER_DESTINATION, isFounderSession, searchNavDestinations, useNavDestinations, type NavDestination } from "@/lib/navDestinations";
import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import { useIsPro } from "@/lib/useIsPro";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";
import { SheetHandle } from "@/components/SheetHandle";
import { PLAYER_SEARCH_MAX_RESULTS, PLAYER_SEARCH_MIN_CHARS, useLeaguePlayerSearchState } from "@/lib/leaguePlayerSearch";
import { PlayerName } from "@/components/PlayerName";

/**
 * web-next's counterpart to mobile's GmOrb.tsx and the Streamlit web app's
 * gm_orb_floating_trigger/render_mobile_destination_sheet (modules/
 * brand_identity.py, app.py) — both of which this port had no equivalent of
 * at all (coridian_, 2026-10-17: "there is still no GM orb on the mobile
 * website"). A floating button, bottom-center, opening a sheet of every
 * destination grouped League / GM Tools / General — the same three-group
 * taxonomy mobile's GmOrb.tsx already established, ported to this app's own
 * real routes rather than mobile's screen names.
 *
 * Mobile-width only (`md:hidden` on the trigger button) — DesktopSidebar
 * is the desktop equivalent of this same destination list (coridian_,
 * 2026-10-17: "desktop side menu").
 *
 * Deliberately smaller than mobile's version for a first pass: no drag-to-
 * reposition, no unread/new-content badges. The core job — "one button gets
 * you anywhere" — is what was completely missing; those refinements are
 * real but separate follow-ups.
 *
 * Search (tap-depth audit 2026-10, #3): one field, same as mobile's orb.
 * It filters the destinations below by label/subtitle and, with a league
 * open, also matches player names from that league's ranked pool (the same
 * pool the Players page searches, fetched once on the first real query).
 * Tapping a player opens their Player Quick View.
 */
export function GmOrb() {
  const [open, setOpen] = useState(false);
  // Swipe-down-to-dismiss (coridian_, 2026-10-18: "you should be able to
  // swipe down from the GM orb to exit out of it or tap off of it to exit
  // out of it") — the shared sheet gesture, lib/useSheetDragDismiss.ts.
  // Tap-off is the backdrop button below; Esc is handled here too.
  const closeSheet = useCallback(() => setOpen(false), []);
  // The header's search icon opens this sheet straight onto the search field.
  const searchRef = useRef<HTMLInputElement>(null);
  const focusSearchNext = useRef(false);
  useEffect(() => {
    const onOpenSearch = () => {
      focusSearchNext.current = true;
      setOpen(true);
    };
    window.addEventListener(OPEN_SEARCH_EVENT, onOpenSearch);
    return () => window.removeEventListener(OPEN_SEARCH_EVENT, onOpenSearch);
  }, []);
  useEffect(() => {
    if (open && focusSearchNext.current) {
      focusSearchNext.current = false;
      searchRef.current?.focus();
    }
  }, [open]);
  const { sheetRef, sheetStyle } = useSheetDragDismiss({ onDismiss: closeSheet, enabled: open });
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open]);
  const { session } = useAuth();
  const { collegeInterest } = useDisplayPreferences();
  const pathname = usePathname();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  const leagueName = searchParams.get("name") || leagueId || "";
  const { coreLeagueDestinations, gmToolsDestinations, generalDestinations, accountDestinations } = useNavDestinations(leagueId, leagueName, collegeInterest);
  // Gold "Pro" markers on paid rows, shown only once we know the plan is Free.
  const showProMarkers = useIsPro() === false;
  // Founder Analytics (coridian_, 2026-10-19: "just put it in the orb menu
  // for the specific account(s) listed on supabase") — gated on the SAME
  // server-issued `founder_ops` app_metadata claim GET /v1/founder/analytics
  // enforces (services/mobile_api_service.py's _founder_analytics_capable).
  // This check is a UX nicety only: supabase-js's session.user.app_metadata
  // comes straight off the verified Supabase Auth session, but the real
  // authorization boundary is that backend 403, not this `if`. A non-
  // founder cannot grant themselves this by editing anything client-side —
  // app_metadata is never writable from the browser (only Supabase's Admin
  // Auth API can set it), unlike user_metadata. Deliberately NOT added to
  // useNavDestinations/navDestinations.ts, since that hook is shared with
  // DesktopSidebar.tsx and has no notion of this per-account gate.
  const founderCapable = isFounderSession(session);

  const { openPlayer } = usePlayerQuickView();
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  // Server-side search over the whole league pool (not just the rankings window).
  const playerSearch = useLeaguePlayerSearchState(leagueId ?? "", "Dynasty", query);
  const wantsPlayers = Boolean(leagueId) && normalizedQuery.length >= PLAYER_SEARCH_MIN_CHARS;

  const destinationResults = useMemo(() => {
    if (!normalizedQuery) return [];
    const searchable = [...(leagueId ? [...coreLeagueDestinations, ...gmToolsDestinations] : []), ...generalDestinations, ...accountDestinations];
    return searchNavDestinations(searchable, normalizedQuery);
  }, [normalizedQuery, leagueId, coreLeagueDestinations, gmToolsDestinations, generalDestinations, accountDestinations]);
  const playerResults = useMemo(() => playerSearch.players.slice(0, PLAYER_SEARCH_MAX_RESULTS), [playerSearch.players]);

  if (!session) return null;
  // Zach, 2026-10-19: "fix the bottom orb on onboard its covering" — "/"
  // is exclusively the signup/Sleeper-import/paywall flow (an already-
  // onboarded signed-in user is always router.replace'd away from it to
  // their league/Portfolio, never shown it) — a floating launcher to jump
  // elsewhere in the app makes no sense mid-onboarding anyway, and its
  // fixed bottom-center position was landing directly on top of the
  // Paywall's own Subscribe button.
  if (pathname === "/") return null;

  return (
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
      <div className="md:hidden" style={{ position: "sticky", bottom: 0, height: 0, zIndex: 40 }}>
      <button
        type="button"
        onClick={() => {
          setQuery("");
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

      {open ? (
        <div className="fixed inset-0" style={{ zIndex: 50 }}>
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0"
            style={{ background: "var(--color-scrim)" }}
            onClick={() => setOpen(false)}
          />
          <div
            ref={sheetRef}
            className="gm-orb-sheet"
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: 0,
              borderTopLeftRadius: "var(--radius-lg, 0)",
              borderTopRightRadius: "var(--radius-lg, 0)",
              boxShadow: "var(--shadow-card)",
              ...sheetStyle,
            }}
          >
            {/* Same animated field-line + sweep texture used app-wide,
                contained to this sheet (not the viewport-fixed global
                layer, which sits behind this sheet's own background) —
                coridian_, 2026-10-18: "that background animation should be
                on the GM orb menu". The sheet's background is a glass tint
                instead of an opaque surface color specifically so this is
                visible, same reasoning as .onboarding-glass. Kept outside
                the scrollable content below so it never scrolls away. */}
            <div className="gm-orb-sheet-field" aria-hidden="true" />
            <div className="gm-orb-sheet-sweep" aria-hidden="true" />
            <div
              className="flex flex-col gap-4 px-5 pt-2 pb-8 overflow-y-auto"
              style={{ position: "relative", zIndex: 1, maxHeight: "78vh" }}
            >
              <SheetHandle />
              <div className="flex flex-col gap-1">
                <span className="text-xs font-bold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "0.03em" }}>
                  {BRAND_NAME}
                </span>
                <span style={{ font: "var(--type-section-title)" }}>Where to go</span>
              </div>

              <input
                ref={searchRef}
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={leagueId ? "Search where to go or a player" : "Search where to go"}
                aria-label={leagueId ? "Search destinations and players" : "Search destinations"}
                autoComplete="off"
                className="filter-input px-3 py-2 text-sm w-full"
              />

              {normalizedQuery ? (
                destinationResults.length > 0 || playerResults.length > 0 ? (
                  <>
                    {destinationResults.length > 0 ? (
                      <div className="flex flex-col">
                        {destinationResults.map((destination) => (
                          <NavRow key={destination.path} destination={destination} showPro={showProMarkers} onNavigate={() => setOpen(false)} />
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
                              setOpen(false);
                              openPlayer({ ...player, leagueId: leagueId ?? undefined, leagueName, sourceLabel: "Search" });
                            }}
                            className="flex items-center gap-3 py-2.5 text-left"
                            style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
                          >
                            <PositionBadge position={player.position} />
                            <span className="flex flex-col min-w-0">
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
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    Searching players…
                  </p>
                ) : (
                  <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    {leagueId ? "No destinations or players match" : "No destinations match"} &ldquo;{query.trim()}&rdquo;.
                  </p>
                )
              ) : (
              <>
              {leagueId ? (
                <NavSection label={leagueName || "League"}>
                  {coreLeagueDestinations.map((destination) => (
                    <NavRow key={destination.path} destination={destination} showPro={showProMarkers} onNavigate={() => setOpen(false)} />
                  ))}
                </NavSection>
              ) : (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  Open a league from Home to unlock Players, Waivers, Trade Analyzer, and more.
                </p>
              )}

              {leagueId ? (
                <NavSection label="GM Tools">
                  {gmToolsDestinations.map((destination) => (
                    <NavRow key={destination.path} destination={destination} showPro={showProMarkers} onNavigate={() => setOpen(false)} />
                  ))}
                </NavSection>
              ) : null}

              <NavSection label="General">
                {generalDestinations.map((destination) => (
                  <NavRow key={destination.path} destination={destination} showPro={showProMarkers} onNavigate={() => setOpen(false)} />
                ))}
              </NavSection>

              <NavSection label="Account">
                {accountDestinations.map((destination) => (
                  <NavRow key={destination.path} destination={destination} showPro={showProMarkers} onNavigate={() => setOpen(false)} />
                ))}
              </NavSection>

              {founderCapable ? (
                <NavSection label="Founder">
                  <NavRow
                    destination={FOUNDER_DESTINATION}
                    onNavigate={() => setOpen(false)}
                  />
                </NavSection>
              ) : null}
              </>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function NavSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-secondary)", letterSpacing: "0.04em" }}>
        {label}
      </span>
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

function NavRow({ destination, showPro = false, onNavigate }: { destination: NavDestination; showPro?: boolean; onNavigate: () => void }) {
  return (
    <Link
      href={destination.path}
      onClick={onNavigate}
      className="flex items-center gap-3 py-2.5"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <span className="shrink-0" style={{ color: destination.color }}>
        <NavDestinationGlyph name={destination.glyph} size={20} />
      </span>
      <span className="flex flex-col min-w-0">
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
