"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";

import { TabGlyph } from "@/components/TabGlyph";
import { Sheet } from "@/components/ui/Sheet";
import { bottomTabBadgeText, simGameBottomTabs, simOrbAriaLabel, activeBottomTab, SIM_NAV_META } from "@/lib/bottomNav";
import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import type { SimTab } from "@/lib/simGameFlow";

/**
 * The Fantasy Sim's own navigation orb (phones). Replaces the global GM orb
 * inside the game: same brand mark, but it names the page you are on and
 * carries a badge for pending trade offers. One tap opens the game navigator
 * (Home, Team, Players, Trades, League, More) with the current page lit, plus
 * All games, Home and search; one tap to go, from anywhere in the scroll.
 *
 * Placement: a slot inside the action bar's one row (Sim to | orb | Advance),
 * centered like FantasyDesk's orb, in flow inside the sticky `.bottom-stack`
 * (never position:fixed or JS-positioned), so it can neither overlap content
 * nor clip. The menu rows reuse the More sheet's look (tinted glyph, subtitle).
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
      <div className="game-orb-slot md:hidden" data-testid="sim-game-orb-dock">
        <button type="button" className="game-orb game-orb--bar" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-label={simOrbAriaLabel(currentTab.label, inbox)} data-testid="sim-game-orb">
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
                <span className="shrink-0" style={{ color: `var(--color-${SIM_NAV_META[t.key]?.tone ?? "accent"})` }}>
                  <TabGlyph name={t.glyph} size={22} />
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-sm font-bold">{t.label}</span>
                  <span className="truncate text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>{SIM_NAV_META[t.key]?.subtitle}</span>
                </span>
                {count ? (
                  <span className="game-orb-badge" style={{ position: "static", transform: "none" }} aria-label={`${t.badge} new`}>
                    {count}
                  </span>
                ) : null}
              </button>
            );
          })}
          <button type="button" className="game-nav-row" onClick={() => { close(); onMore(); }}>
            <span className="shrink-0" style={{ color: "var(--color-accent)" }}>
              <TabGlyph name="more" size={22} />
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="text-sm font-bold">More</span>
              <span className="truncate text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>{SIM_NAV_META.more.subtitle}</span>
            </span>
          </button>
        </nav>
        <div className="mt-3 flex flex-col gap-1 border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
          <button type="button" className="game-nav-row" onClick={() => { close(); window.setTimeout(() => window.dispatchEvent(new Event(OPEN_SEARCH_EVENT)), 0); }}>
            <svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="var(--color-diagnostic)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <span className="flex-1">Search players and pages</span>
          </button>
          <button type="button" className="game-nav-row" onClick={() => { close(); onHub(); }}>
            <span className="shrink-0" style={{ color: "var(--color-premium)" }}><TabGlyph name="league" size={22} /></span>
            <span className="flex-1">All games</span>
          </button>
          <Link href="/" className="game-nav-row" onClick={close}>
            <span className="shrink-0" style={{ color: "var(--color-accent)" }}><TabGlyph name="home" size={22} /></span>
            <span className="flex-1">Back to FantasyDesk home</span>
          </Link>
        </div>
      </Sheet>
    </>
  );
}
