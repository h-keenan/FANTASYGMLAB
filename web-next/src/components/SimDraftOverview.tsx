"use client";

import { SimDraftGrid } from "@/components/SimDraftGrid";
import { Sheet } from "@/components/ui/Sheet";
import { CompactModule } from "@/components/ui/CompactModule";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import { LetterGrade } from "@/components/ui/LetterGrade";
import { SimTeamIdentity } from "@/components/SimTeamIdentity";
import { positionColorVar } from "@/lib/playerPresentation";
import { simDraftMiniBoard, simDraftMiniWindow, simDraftPickChip, simDraftProgress, simDraftRecentPicks, simRookieMiniBoard, simRookieRecentCards, simRookieRecentChips, type SimMiniCell, type SimRecentPickCard, type SimSurvival } from "@/lib/simDraft";
import type { SimDraftState, SimGamePlayer } from "@/lib/simGame";

/**
 * "Who has been drafted", always on the draft page (not behind a tab). The recent picks live in the pinned clock area
 * (`SimRecentStrip`, below); this is the mini board module under it: rounds x teams of tiny position-coloured cells, your
 * column outlined, the pick on the clock ringed, rounds around the clock; "Full board" opens the whole grid
 * (`onFullBoard`, the page owns the sheet). Mobile twin: SimDraftOverview.tsx.
 */
export function SimDraftOverview({ draft, teams, onFullBoard }: { draft: SimDraftState; teams: number; onFullBoard: () => void }) {
  const recent = simDraftRecentPicks(draft.picks, 1);
  const progress = simDraftProgress(draft, teams);
  const mini = simDraftMiniBoard(draft, teams);
  const win = simDraftMiniWindow(mini.rows, progress.round);
  const mine = (draft.picks ?? []).filter((p) => draft.teams?.find((t) => t.team_id === p.team_id)?.is_you).length;
  const last = recent[0];
  return (
    <div className="flex flex-col gap-2" data-testid="draft-overview">
      <CompactModule
        id="draft.board"
        title="Draft board"
        tone="accent"
        defaultOpen
        parts={[
          { key: "n", text: `${progress.made}/${progress.total} picks`, strong: true },
          last ? { key: "last", text: `last ${simDraftPickChip(last)}` } : null,
          { key: "mine", text: `you ${mine}`, tone: "accent" },
        ]}
      >
        <SimMiniBoard rows={win.rows} from={win.from} to={win.to} />
        <button type="button" className="tap-link self-start text-xs font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }} onClick={onFullBoard}>
          Full board
        </button>
      </CompactModule>
    </div>
  );
}

/** The full draft grid in a sheet (the strip's "Full board" and the board module's link both open it). */
export function SimFullBoardSheet({ open, onClose, draft, teams, onOpen }: { open: boolean; onClose: () => void; draft: SimDraftState; teams: number; onOpen: (player: SimGamePlayer) => void }) {
  return (
    <Sheet open={open} onClose={onClose} title="Full draft board" size="lg">
      <SimDraftGrid draft={draft} teams={teams} onOpen={(p) => { onClose(); onOpen(p); }} />
    </Sheet>
  );
}

/**
 * The latest picks as a horizontally scrolling strip of compact player cards (coridian_: "the prior picks with the prior
 * players taken"): pick number, the picking team's logo (SimTeamIdentity), avatar, name, position and letter grade. A card
 * opens the player; "Full board" opens the whole board. Lives in the pinned clock area (redraft and rookie drafts).
 */
export function SimRecentStrip({ cards, onOpenPlayer, onFullBoard }: { cards: SimRecentPickCard[]; onOpenPlayer?: (card: SimRecentPickCard) => void; onFullBoard?: () => void }) {
  return (
    <div className="flex flex-col gap-1" data-testid="recent-picks-wrap">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>Just drafted</span>
        {onFullBoard ? (
          <button type="button" onClick={onFullBoard} className="tap-link text-xs font-bold" style={{ color: "var(--color-accent)", minHeight: 28 }} data-testid="recent-full-board">
            Full board
          </button>
        ) : null}
      </div>
      <ol className="flex gap-2 overflow-x-auto pb-1" aria-label="Recent picks" data-testid="recent-picks" style={{ scrollbarWidth: "none" }}>
        {cards.length === 0 ? (
          <li className="text-xs" style={{ color: "var(--color-text-muted)", minHeight: 40, display: "flex", alignItems: "center" }}>No picks yet. The first ones land here.</li>
        ) : (
          cards.map((card, i) => (
            <li key={card.key} className={i === 0 ? "enter-rise shrink-0" : "shrink-0"} style={{ width: 168 }} data-testid="recent-pick-card">
              <button
                type="button"
                onClick={onOpenPlayer ? () => onOpenPlayer(card) : undefined}
                disabled={!onOpenPlayer}
                aria-label={card.aria}
                className="flex w-full flex-col gap-1 p-2 text-left"
                style={{ background: "var(--color-surface-muted)", borderRadius: "var(--radius-control)", border: card.isYou ? "1px solid var(--color-accent)" : "1px solid transparent", color: "inherit" }}
              >
                <span className="flex items-center justify-between gap-1 text-[0.6875rem] font-extrabold tabular-nums" style={{ color: "var(--color-text-muted)" }}>
                  <span>{card.pickLabel}</span>
                  {card.teamName ? <SimTeamIdentity name={card.teamName} size="chip" hideName /> : null}
                </span>
                <CompactPlayerCard
                  player={card.player}
                  testId="recent-pick-player"
                  trailing={card.grade ? <LetterGrade grade={card.grade} size="xs" /> : undefined}
                />
              </button>
            </li>
          ))
        )}
      </ol>
    </div>
  );
}

/** "Who survives to my pick": one calm line from public ADP, a running position and your needs (`simDraftSurvival`). */
export function SimSurvivalLine({ survival }: { survival: SimSurvival | null }) {
  if (!survival) return null;
  return (
    <p className="enter-rise text-xs" style={{ color: "var(--color-text-secondary)" }} data-testid="draft-survival">
      <span className="font-extrabold" style={{ color: "var(--color-accent)" }}>Before your pick </span>
      {survival.text}
    </p>
  );
}

/** Rounds x picks of tiny position-coloured cells: yours outlined, the pick on the clock ringed, open slots dashed. */
export function SimMiniBoard({ rows, from, to }: { rows: SimMiniCell[][]; from: number; to: number }) {
  return (
    <div className="flex flex-col gap-1" data-testid="mini-board" role="img" aria-label={`Mini draft board, rounds ${from} to ${to}`}>
      {rows.map((row, i) => (
        <div key={from + i} className="flex items-center gap-1">
          <span className="shrink-0 text-[0.6875rem] font-extrabold tabular-nums" style={{ width: 22, color: "var(--color-text-muted)" }}>R{from + i}</span>
          <div className="grid min-w-0 flex-1 gap-[3px]" style={{ gridTemplateColumns: `repeat(${row.length}, minmax(0, 1fr))` }}>
            {row.map((cell) => {
              const colorVar = cell.pos ? positionColorVar(cell.pos) : undefined;
              return (
                <span
                  key={cell.key}
                  title={cell.pickNo ? `#${cell.pickNo}${cell.pos ? ` ${cell.pos}` : ""}` : undefined}
                  style={{
                    height: 18,
                    borderRadius: 4,
                    background: colorVar ? `var(${colorVar})` : "transparent",
                    border: cell.clock ? "2px solid var(--color-action)" : cell.pos ? "none" : "1px dashed var(--color-border)",
                    outline: cell.you ? "1.5px solid var(--color-accent)" : undefined,
                    outlineOffset: 1,
                  }}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/** The rookie draft's always-visible "who has been drafted": the recent strip plus the mini board in a CompactModule. */
export function SimRookieOverview({ order, onClockPick, round, made, total }: { order: readonly { n: number; round: number; pick: string; is_yours: boolean; made: { id: string; name: string; pos: string } | null }[]; onClockPick: string | null | undefined; round: number; made: number; total: number }) {
  const rows = simRookieMiniBoard(order, onClockPick);
  const win = simDraftMiniWindow(rows, round);
  const cards = simRookieRecentCards(order);
  const last = simRookieRecentChips(order, 1)[0];
  return (
    <div className="flex flex-col gap-2" data-testid="rookie-overview">
      <SimRecentStrip cards={cards} />
      <CompactModule id="rookie.board" title="Draft board" defaultOpen parts={[{ key: "n", text: `${made}/${total} picks`, strong: true }, last ? { key: "last", text: `last ${last.label}` } : null]}>
        <SimMiniBoard rows={win.rows} from={win.from} to={win.to} />
      </CompactModule>
    </div>
  );
}
