"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { BRAND_NAME } from "@/lib/brand";
import { NavDestinationGlyph } from "@/components/NavDestinationGlyph";
import { useNavDestinations, type NavDestination } from "@/lib/navDestinations";

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
 * reposition, no destination search, no unread/new-content badges. The core
 * job — "one button gets you anywhere" — is what was completely missing;
 * those refinements are real but separate follow-ups.
 */
export function GmOrb() {
  const [open, setOpen] = useState(false);
  // Swipe-down-to-dismiss, same pattern PlayerQuickView.tsx already uses
  // for its own bottom sheet — coridian_, 2026-10-18: "you should be able
  // to swipe down from the GM orb to exit out of it or tap off of it to
  // exit out of it" (tap-off already worked, via the backdrop button below).
  const dragStartY = useRef<number | null>(null);
  const [dragY, setDragY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const DISMISS_THRESHOLD_PX = 110;

  function handleDragStart(event: React.PointerEvent<HTMLDivElement>) {
    dragStartY.current = event.clientY;
    setIsDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function handleDragMove(event: React.PointerEvent<HTMLDivElement>) {
    if (dragStartY.current === null) return;
    setDragY(Math.max(0, event.clientY - dragStartY.current));
  }
  function handleDragEnd() {
    if (dragY > DISMISS_THRESHOLD_PX) {
      setOpen(false);
    }
    dragStartY.current = null;
    setIsDragging(false);
    setDragY(0);
  }
  const { session } = useAuth();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  const leagueName = searchParams.get("name") || leagueId || "";
  const { coreLeagueDestinations, gmToolsDestinations, generalDestinations } = useNavDestinations(leagueId, leagueName);

  if (!session) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open GM menu"
        // coridian_, 2026-10-18: "Gm orb is still too high" — bottom-6
        // (24px) left too much empty space below it; bottom-3 (12px) sits
        // closer to the true bottom edge.
        className="fixed bottom-3 left-1/2 flex items-center justify-center md:hidden"
        style={{
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
        <Image src="/brand-mark.png" alt="" width={28} height={28} className="brand-mark-icon" style={{ objectFit: "contain" }} />
      </button>

      {open ? (
        <div className="fixed inset-0" style={{ zIndex: 50 }}>
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0"
            style={{ background: "rgba(0,0,0,0.55)" }}
            onClick={() => setOpen(false)}
          />
          <div
            className="gm-orb-sheet"
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: 0,
              borderTopLeftRadius: "var(--radius-lg, 0)",
              borderTopRightRadius: "var(--radius-lg, 0)",
              boxShadow: "var(--shadow-card)",
              transform: dragY ? `translateY(${dragY}px)` : undefined,
              transition: isDragging ? "none" : "transform 180ms ease",
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
              <div
                className="gm-orb-drag-handle"
                onPointerDown={handleDragStart}
                onPointerMove={handleDragMove}
                onPointerUp={handleDragEnd}
                onPointerCancel={handleDragEnd}
                aria-hidden="true"
              >
                <span className="gm-orb-drag-handle-bar" />
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs font-bold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "0.03em" }}>
                  {BRAND_NAME}
                </span>
                <span style={{ font: "var(--type-section-title)" }}>Where to go</span>
              </div>

              {leagueId ? (
                <NavSection label={leagueName || "League"}>
                  {coreLeagueDestinations.map((destination) => (
                    <NavRow key={destination.path} destination={destination} onNavigate={() => setOpen(false)} />
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
                    <NavRow key={destination.path} destination={destination} onNavigate={() => setOpen(false)} />
                  ))}
                </NavSection>
              ) : null}

              <NavSection label="General">
                {generalDestinations.map((destination) => (
                  <NavRow key={destination.path} destination={destination} onNavigate={() => setOpen(false)} />
                ))}
              </NavSection>
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

function NavRow({ destination, onNavigate }: { destination: NavDestination; onNavigate: () => void }) {
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
        <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
          {destination.label}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {destination.subtitle}
        </span>
      </span>
    </Link>
  );
}
