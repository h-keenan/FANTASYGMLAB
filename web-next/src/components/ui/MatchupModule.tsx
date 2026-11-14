"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import { ToneBadge } from "@/components/ToneBadge";
import { matchupTickerParts, type MatchupCardModel, type MatchupSwingPlayer } from "@/lib/matchupModules";
import { compactSummaryText } from "@/lib/compactModule";
import { playerSurname } from "@/lib/playerNameDisplay";

/**
 * THE matchup module (docs/ui-patterns.md, "Matchup hero and ticker"). One model (`matchupCardModel`), two forms:
 *   MatchupHeroCard  the page form (Matchup page, Fantasy Sim Home): week + live state, win chance chip, both scores,
 *                    the win bar, a projection / players-left line and two swing players with avatars (the widest
 *                    projection range still to play on each side). Tapping a swing player opens the player peek.
 *   MatchupTicker    the compact form for stacks: "WK 7 · You 112.4 - 98.1 Mike · 71%", one tap to the Matchup page.
 * Cyan / neutral glass only, gold never. Mobile twin: mobile/src/components/MatchupModule.tsx.
 */

const TONE = { success: "var(--color-success)", danger: "var(--color-danger)", accent: "var(--color-accent)" } as const;

export function MatchupHeroCard({
  model,
  onOpenPlayer,
  action,
  testId = "matchup-hero",
  children,
}: {
  model: MatchupCardModel;
  /** Avatar tap: opens the player peek (web Quick View, sim player sheet). */
  onOpenPlayer?: (player: MatchupSwingPlayer) => void;
  /** The one primary action ("Open lineup"). */
  action?: ReactNode;
  testId?: string;
  children?: ReactNode;
}) {
  const winTone = model.win ? TONE[model.win.tone] : "var(--color-accent)";
  return (
    <AccentCard accent="var(--color-accent-strong)" as="section" data-testid={testId}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }} data-testid="matchup-kicker">
          {model.kicker}
        </span>
        {model.win ? <ToneBadge label={model.win.label} color={winTone} testId="matchup-win-chip" /> : null}
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-2" role="group" aria-label={`${model.mine.name} ${model.mine.score}, ${model.opponent.name} ${model.opponent.score}`}>
        <span className="flex min-w-0 flex-col">
          <span className="text-3xl font-extrabold tabular-nums leading-none" data-testid="matchup-my-score">
            {model.mine.score}
          </span>
          <span className="break-words text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {model.mine.name}
          </span>
        </span>
        <span className="pb-1 text-xs font-extrabold" style={{ color: "var(--color-text-muted)" }} aria-hidden="true">
          vs
        </span>
        <span className="flex min-w-0 flex-col items-end text-right">
          <span className="text-3xl font-extrabold tabular-nums leading-none" style={{ color: "var(--color-text-secondary)" }} data-testid="matchup-opp-score">
            {model.opponent.score}
          </span>
          <span className="max-w-full break-words text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {model.opponent.name}
          </span>
        </span>
      </div>
      {model.bar != null ? (
        <div
          className="h-2 w-full overflow-hidden"
          style={{ borderRadius: "var(--radius-pill)", background: "color-mix(in srgb, var(--color-danger) 28%, var(--color-surface-muted))" }}
          role="img"
          aria-label={`Win chance ${model.bar}%`}
        >
          <div className="h-full" style={{ width: `${model.bar}%`, background: "var(--color-success)" }} />
        </div>
      ) : null}
      <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="matchup-detail">
        {[model.basis === "projected" ? "Projected points" : null, model.detail].filter(Boolean).join(" · ")}
      </p>
      {model.swing.length > 0 ? (
        <div className="flex flex-col gap-1 pt-1" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }} data-testid="matchup-swing">
          <span className="pt-2 text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Swing players
          </span>
          <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0">
            {model.swing.map((p) => {
              const body = (
                <>
                  <PlayerAvatar playerId={p.playerId} tier={p.tier} size={36} fallbackLabel={p.name.trim().slice(0, 1)} />
                  <span className="flex min-w-0 flex-col text-left">
                    <span className="flex items-center gap-1">
                      <span className="min-w-0 break-words text-sm font-bold">{playerSurname(p.name) || p.name}</span>
                      {p.position ? <PositionBadge position={p.position} /> : null}
                    </span>
                    <span className="text-xs font-bold" style={{ color: p.side === "mine" ? "var(--color-accent)" : "var(--color-text-secondary)" }}>
                      {p.label}
                    </span>
                  </span>
                </>
              );
              return (
                <li key={p.key} className="min-w-0" data-testid="matchup-swing-player">
                  {onOpenPlayer ? (
                    <button type="button" className="flex w-full items-center gap-2" style={{ minHeight: "var(--touch-target-min)", color: "inherit" }} aria-label={`${p.name}, ${p.label}. Open player`} onClick={() => onOpenPlayer(p)}>
                      {body}
                    </button>
                  ) : (
                    <div className="flex w-full items-center gap-2" style={{ minHeight: "var(--touch-target-min)" }}>
                      {body}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {action}
      {children}
    </AccentCard>
  );
}

export function MatchupTicker({ model, week, href, testId = "matchup-ticker" }: { model: MatchupCardModel; week: number | null; href: string; testId?: string }) {
  const parts = matchupTickerParts(model, week);
  const winColor = model.win ? TONE[model.win.tone] : null;
  return (
    <AccentCard accent="var(--color-accent)" as="section" compact data-testid={testId}>
      <Link href={href} aria-label={`Matchup: ${compactSummaryText(parts)}. Open`} className="flex items-center gap-2" style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }}>
        <span className="w-11 shrink-0 text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)" }}>
          {parts[0].text}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-extrabold tabular-nums">{parts[1].text}</span>
        {model.win && winColor ? <ToneBadge label={`${model.win.pct}%`} color={winColor} /> : null}
        <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
          →
        </span>
      </Link>
    </AccentCard>
  );
}
