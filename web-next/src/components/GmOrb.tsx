"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/context/AuthContext";

interface Destination {
  label: string;
  path: string;
  subtitle: string;
}

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
 * Deliberately smaller than mobile's version for a first pass: no drag-to-
 * reposition, no destination search, no unread/new-content badges. The core
 * job — "one button gets you anywhere" — is what was completely missing;
 * those refinements are real but separate follow-ups.
 */
export function GmOrb() {
  const [open, setOpen] = useState(false);
  const { session } = useAuth();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  const leagueName = searchParams.get("name") || leagueId || "";
  const query = leagueId ? `?name=${encodeURIComponent(leagueName)}` : "";

  if (!session) return null;

  const coreLeagueDestinations: Destination[] = leagueId
    ? [
        { label: "Dashboard", path: `/dashboard/${encodeURIComponent(leagueId)}${query}`, subtitle: "Personalized insights and recommendations" },
        { label: "Alerts", path: `/alerts/${encodeURIComponent(leagueId)}${query}`, subtitle: "Injuries, news, and important updates" },
        { label: "My Team", path: `/my-team/${encodeURIComponent(leagueId)}${query}`, subtitle: "Roster, lineup, and team analysis" },
        { label: "Matchup", path: `/matchup/${encodeURIComponent(leagueId)}${query}`, subtitle: "This week's matchup and comparison" },
        { label: "Waivers", path: `/waivers/${encodeURIComponent(leagueId)}${query}`, subtitle: "Top adds, trends, and free agents" },
        { label: "Players", path: `/players/${encodeURIComponent(leagueId)}${query}`, subtitle: "Search, rankings, and player insights" },
        { label: "League Rankings", path: `/league-rankings/${encodeURIComponent(leagueId)}${query}`, subtitle: "Power rankings across the league" },
      ]
    : [];

  const gmToolsDestinations: Destination[] = leagueId
    ? [
        { label: "Trade Hub", path: `/trade-hub/${encodeURIComponent(leagueId)}${query}`, subtitle: "Trade ideas, ranked by fit" },
        { label: "Trade Finder", path: `/trade-finder/${encodeURIComponent(leagueId)}${query}`, subtitle: "Build and search for a trade" },
        { label: "Trade Analyzer", path: `/trade-analyzer/${encodeURIComponent(leagueId)}${query}`, subtitle: "Evaluate any trade package" },
        { label: "GM Targets", path: `/gm-targets/${encodeURIComponent(leagueId)}${query}`, subtitle: "Your saved watchlist" },
        { label: "Team Situation", path: `/team-situation/${encodeURIComponent(leagueId)}${query}`, subtitle: "Declare your rebuild/compete stance" },
        { label: "GM Plan", path: `/gm-plan/${encodeURIComponent(leagueId)}${query}`, subtitle: "Your season-long roadmap" },
        { label: "Draft Center", path: `/draft-center/${encodeURIComponent(leagueId)}${query}`, subtitle: "Picks, order, and draft tools" },
        { label: "Live Draft", path: `/live-draft/${encodeURIComponent(leagueId)}${query}`, subtitle: "Real-time draft room" },
        { label: "League Recaps", path: `/league-recaps/${encodeURIComponent(leagueId)}${query}`, subtitle: "Weekly league recap and stories" },
      ]
    : [];

  const generalDestinations: Destination[] = [
    { label: "Home", path: "/", subtitle: "Switch leagues and manage account" },
    { label: "Portfolio", path: "/portfolio", subtitle: "Your standing across every saved league" },
    { label: "News", path: "/news", subtitle: "Latest NFL news and updates" },
    { label: "Trade History", path: "/trade-history", subtitle: "Trades you've shared and confirmed" },
    { label: "College Scouting", path: "/college-scouting", subtitle: "Grade incoming prospects" },
  ];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open GM menu"
        className="fixed bottom-6 left-1/2 flex items-center justify-center"
        style={{
          transform: "translateX(-50%)",
          width: "3.25rem",
          height: "3.25rem",
          borderRadius: "50%",
          background: "var(--color-background)",
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
        <Image src="/brand-mark.png" alt="" width={30} height={20} style={{ objectFit: "contain" }} />
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
            className="absolute left-0 right-0 bottom-0 flex flex-col gap-4 px-5 pt-4 pb-8 overflow-y-auto"
            style={{
              maxHeight: "78vh",
              background: "var(--color-surface-secondary)",
              borderTopLeftRadius: "var(--radius-lg, 0)",
              borderTopRightRadius: "var(--radius-lg, 0)",
              boxShadow: "var(--shadow-card)",
            }}
          >
            <div className="flex flex-col gap-1">
              <span className="text-xs font-bold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "0.03em" }}>
                FantasyGM Lab
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

function NavRow({ destination, onNavigate }: { destination: Destination; onNavigate: () => void }) {
  return (
    <Link
      href={destination.path}
      onClick={onNavigate}
      className="flex flex-col py-2.5"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        {destination.label}
      </span>
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {destination.subtitle}
      </span>
    </Link>
  );
}
