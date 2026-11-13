"use client";

import type { ReactNode } from "react";
import { SimCrest } from "@/components/SimCrest";
import { SimGlyph } from "@/components/SimGlyph";
import { simStatusChips, simCompactSeason, simCompactWeek } from "@/lib/bottomNav";
import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import { simFmtRecord, type SimGame } from "@/lib/simGame";
import type { SimTab } from "@/lib/simGameFlow";

const ICON_BTN = "inline-flex shrink-0 items-center justify-center";
const ICON_STYLE = { width: "var(--touch-target-min)", height: "var(--touch-target-min)", color: "var(--color-text-secondary)" } as const;

/**
 * The phone game header: one line, replacing the app header, the "All games /
 * Week / Season / team" block and the pre-advance notes (they become chips,
 * SimStatusChips). Back arrow to All games, "Wk 3/14 . S1/5", the team as a
 * tappable chip (opens the team sheet), search (the GM menu's search) and the
 * overflow menu (Rules, Reset week, Delete). Phones only (md:hidden); desktop
 * keeps its own header. Mobile twin: mobile/src/components/SimGameHeader.tsx.
 */
export function SimGameHeader({ game, onHub, onTeam, onMore, bell }: { game: SimGame; onHub: () => void; onTeam: (teamId: string) => void; onMore: () => void; bell?: ReactNode }) {
  const you = game.you;
  const season = simCompactSeason(game.dynasty);
  const showTeam = Boolean(you) && game.phase !== "draft";
  return (
    <header className="sim-game-header md:hidden" data-testid="sim-game-header">
      <button type="button" className={ICON_BTN} style={ICON_STYLE} onClick={onHub} aria-label="Back to all games">
        <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m15 18-6-6 6-6" />
        </svg>
      </button>
      <h2 className="shrink-0 text-sm font-extrabold leading-none whitespace-nowrap" data-testid="game-heading-phone">
        {simCompactWeek(game)}
        {season ? (
          <span className="ml-1.5 text-xs font-bold" style={{ color: "var(--color-text-muted)" }} data-testid="dynasty-progress-phone" title="Season">
            {season}
          </span>
        ) : null}
      </h2>
      {showTeam && you ? (
        <button
          type="button"
          className="sim-team-chip"
          onClick={() => you.team_id && onTeam(you.team_id)}
          aria-label={`Your team: ${you.name}, ${simFmtRecord(you)}. Open team`}
          data-testid="sim-team-chip"
        >
          <SimCrest name={you.name} size={20} />
          <span className="min-w-0 flex-1 break-words text-xs font-bold">{you.name}</span>
          <span className="shrink-0 text-xs tabular-nums" style={{ color: "var(--color-text-muted)" }}>{simFmtRecord(you)}</span>
        </button>
      ) : (
        <span className="flex-1" />
      )}
      {bell}
      <button type="button" className={ICON_BTN} style={ICON_STYLE} onClick={() => window.dispatchEvent(new Event(OPEN_SEARCH_EVENT))} aria-label="Search players and pages">
        <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      </button>
      <button type="button" className={ICON_BTN} style={ICON_STYLE} onClick={onMore} aria-haspopup="dialog" aria-label="Game menu: rules, reset week, delete">
        <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <circle cx="5" cy="12" r="1.8" />
          <circle cx="12" cy="12" r="1.8" />
          <circle cx="19" cy="12" r="1.8" />
        </svg>
      </button>
    </header>
  );
}

/** The pre-advance notes as small tappable chips under the header (phones). Each jumps to the tab that fixes it. */
export function SimStatusChips({ game, onTab }: { game: SimGame; onTab: (tab: SimTab) => void }) {
  const chips = simStatusChips(game.pending);
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
