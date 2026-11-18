"use client";

import { useEffect, useState, type ReactNode } from "react";
import { SimTeamLogo } from "@/components/SimTeamIdentity";
import { SimGlyph } from "@/components/SimGlyph";
import { ribbonCollapsed } from "@/lib/appHeader";
import { simStatusChips, simCompactSeason, simCompactWeek } from "@/lib/bottomNav";
import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import { simFmtRecord, type SimGame } from "@/lib/simGame";
import type { SimTab } from "@/lib/simGameFlow";

export const SIM_ICON_BTN = "inline-flex shrink-0 items-center justify-center";
export const SIM_ICON_STYLE = { width: "var(--touch-target-min)", height: "var(--touch-target-min)", color: "var(--color-text-secondary)" } as const;

/**
 * The phone game header, on the same V2 anatomy as the Desk shell header (UI pass 7, docs/audits/2026-11-header-rewrite.md): ONE 52px row (back
 * to All games, your team as a tappable crest chip whose name wraps and never truncates, the bell, search, the game menu) plus a ribbon of
 * glanceable chips (week, season, record) that folds away after 24px of scroll. It used to be 97px at every width (an icon row plus a
 * full-width team row). Phones only (md:hidden); desktop keeps its own header. Mobile twin: mobile/src/components/SimGameHeader.tsx.
 */
export function SimGameHeader({ game, onHub, onTeam, onMore, bell }: { game: SimGame; onHub: () => void; onTeam: (teamId: string) => void; onMore: () => void; bell?: ReactNode }) {
  const you = game.you;
  const season = simCompactSeason(game.dynasty);
  const drafting = game.phase === "draft";
  const showTeam = Boolean(you) && !drafting;
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    let was = false;
    const onScroll = () => {
      const next = ribbonCollapsed(window.scrollY, was);
      if (next !== was) {
        was = next;
        setCollapsed(next);
      }
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header className="sim-game-header md:hidden" data-testid="sim-game-header" data-collapsed={collapsed ? "true" : "false"}>
      <div className="sim-game-header-row">
        <button type="button" className={SIM_ICON_BTN} style={SIM_ICON_STYLE} onClick={onHub} aria-label="Back to all games">
          <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
        {showTeam && you ? (
          <button type="button" className="sim-team-chip" onClick={() => you.team_id && onTeam(you.team_id)} data-testid="sim-team-chip">
            <SimTeamLogo name={you.name} size="chip" />
            <span className="min-w-0 flex-1 break-words text-sm font-extrabold leading-tight">{you.name}</span>
            <span className="sr-only">. Your team, open team</span>
          </button>
        ) : drafting ? (
          // The draft room's immersive minimal chrome: back + title on ONE line, no ribbon row under it.
          <h2 className="min-w-0 flex-1 text-sm font-extrabold" style={{ color: "var(--color-accent)" }} data-testid="game-heading-phone">{simCompactWeek(game)}</h2>
        ) : (
          <span className="flex-1" />
        )}
        {bell}
        <button type="button" className={SIM_ICON_BTN} style={SIM_ICON_STYLE} onClick={() => window.dispatchEvent(new Event(OPEN_SEARCH_EVENT))} aria-label="Search players and pages">
          <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
        </button>
        <button type="button" className={SIM_ICON_BTN} style={SIM_ICON_STYLE} onClick={onMore} aria-haspopup="dialog" aria-label="Game menu: rules, reset week, delete">
          <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <circle cx="5" cy="12" r="1.8" />
            <circle cx="12" cy="12" r="1.8" />
            <circle cx="19" cy="12" r="1.8" />
          </svg>
        </button>
      </div>
      {drafting ? null : <div className="shell-header-ribbon" role="group" aria-label="This game at a glance">
        <div className="shell-header-ribbon-inner" tabIndex={0}>
          <h2 className="shell-header-chip" style={{ color: "var(--color-accent)" }} data-testid="game-heading-phone">{simCompactWeek(game)}</h2>
          {season ? (
            <span className="shell-header-chip" style={{ color: "var(--color-text-secondary)" }} data-testid="dynasty-progress-phone" title="Season">{season}</span>
          ) : null}
          {showTeam && you ? <span className="shell-header-chip" style={{ color: "var(--color-text-secondary)" }}>{simFmtRecord(you)}</span> : null}
        </div>
      </div>}
    </header>
  );
}

/** The pre-advance notes as small tappable chips under the header (phones). Each jumps to the tab that fixes it. */
export function SimStatusChips({ game, onTab }: { game: SimGame; onTab: (tab: SimTab) => void }) {
  const chips = simStatusChips(game.pending, game);
  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 md:hidden" role="group" aria-label="Before you advance" data-testid="sim-status-chips">
      {chips.map((chip) => {
        const color = chip.tone === "warning" ? "var(--color-warning)" : "var(--color-accent)";
        return (
          <button
            key={chip.key}
            type="button"
            className="inline-flex items-center gap-1.5 px-3 text-xs font-bold"
            style={{
              minHeight: "var(--touch-target-min)",
              borderRadius: "var(--radius-pill)",
              color,
              border: `1px solid color-mix(in srgb, ${color} 45%, transparent)`,
              background: `color-mix(in srgb, ${color} 10%, transparent)`,
            }}
            onClick={() => onTab(chip.tab)}
          >
            <SimGlyph name={chip.tone === "warning" ? "alert" : "trade"} size={14} />
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
