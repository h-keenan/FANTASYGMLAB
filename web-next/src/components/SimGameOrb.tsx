"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { TabGlyph } from "@/components/TabGlyph";
import { Sheet } from "@/components/ui/Sheet";
import { bottomTabBadgeText, simGameBottomTabs, simOrbAriaLabel, activeBottomTab } from "@/lib/bottomNav";
import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import type { SimTab } from "@/lib/simGameFlow";

/**
 * The Fantasy Sim's own navigation orb (phones). Replaces the global GM orb
 * inside the game: same brand mark, but it names the page you are on and
 * carries a badge for pending trade offers. One tap opens the game navigator
 * (Home, Team, Players, Trades, League, More) with the current page lit, plus
 * All games, Home and search; one tap to go, from anywhere in the scroll.
 *
 * Placement: rendered inside the game's in-flow sticky `.bottom-stack`
 * (`.game-orb-dock`, absolute inside the stack, never position:fixed or
 * JS-positioned), docked bottom-right directly above the Advance pill.
 * Mobile twin: mobile/src/components/SimGameOrb.tsx.
 */
export function SimGameOrb({
  tab,
  offseason,
  inbox,
  onTab,
  onMore,
  onHub,
}: {
  tab: SimTab;
  offseason: boolean;
  inbox: number;
  onTab: (tab: SimTab) => void;
  onMore: () => void;
  onHub: () => void;
}) {
  const [open, setOpen] = useState(false);
  const tabs = simGameBottomTabs({ offseason, inbox });
  const current = activeBottomTab(tabs, tab);
  const currentTab = tabs.find((t) => t.key === current) ?? tabs[0];
  const badge = bottomTabBadgeText(inbox);
  const close = () => setOpen(false);

  return (
    <>
      <div className="game-orb-dock" data-testid="sim-game-orb-dock">
        <button type="button" className="game-orb" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label={simOrbAriaLabel(currentTab.label, inbox)} data-testid="sim-game-orb">
          <Image src="/brand-mark.png" alt="" width={18} height={18} className="brand-mark-icon" style={{ objectFit: "contain" }} />
          <span className="game-orb-label" aria-hidden="true">{currentTab.label}</span>{badge ? " " : null}
          {badge ? <span className="game-orb-badge" aria-hidden="true" data-testid="sim-game-orb-badge">{badge}</span> : null}
        </button>
      </div>
      <Sheet open={open} onClose={close} title="Fantasy Sim" description="Jump to any page of this game.">
        <nav aria-label="Game pages" className="flex flex-col gap-1" data-testid="sim-game-nav">
          {tabs.map((t) => {
            const count = bottomTabBadgeText(t.badge);
            return (
              <button
                key={t.key}
                type="button"
                className="game-nav-row"
                aria-current={t.key === current ? "page" : undefined}
                onClick={() => {
                  close();
                  onTab(t.key as SimTab);
                }}
              >
                <TabGlyph name={t.glyph} size={22} />
                <span className="flex-1">{t.label}</span>
                {count ? (
                  <span className="game-orb-badge" style={{ position: "static" }} aria-label={`${t.badge} new`}>
                    {count}
                  </span>
                ) : null}
              </button>
            );
          })}
          <button type="button" className="game-nav-row" onClick={() => { close(); onMore(); }}>
            <TabGlyph name="more" size={22} />
            <span className="flex-1">More: rules, reset week, delete</span>
          </button>
        </nav>
        <div className="mt-3 flex flex-col gap-1 border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
          <button type="button" className="game-nav-row" onClick={() => { close(); window.setTimeout(() => window.dispatchEvent(new Event(OPEN_SEARCH_EVENT)), 0); }}>
            <svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <span className="flex-1">Search players and pages</span>
          </button>
          <button type="button" className="game-nav-row" onClick={() => { close(); onHub(); }}>
            <TabGlyph name="league" size={22} />
            <span className="flex-1">All games</span>
          </button>
          <Link href="/" className="game-nav-row" onClick={close}>
            <TabGlyph name="home" size={22} />
            <span className="flex-1">Back to FantasyDesk home</span>
          </Link>
        </div>
      </Sheet>
    </>
  );
}
