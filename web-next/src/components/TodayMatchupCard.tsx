"use client";

import Link from "next/link";
import { useId, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { StatusRingMark } from "@/components/ui/StatusHeader";
import { SwingPlayers } from "@/components/ui/MatchupModule";
import { Collapse } from "@/components/ui/Presence";
import { ToneBadge } from "@/components/ToneBadge";
import type { MatchupResponse } from "@/lib/api";
import { matchupSwingPlayers, swingInputsFromMatchup } from "@/lib/matchupModules";
import { statusRing } from "@/lib/statusHeader";
import type { TeamStatusMatchup } from "@/lib/teamStatus";
import { todayMatchupRing } from "@/lib/todayView";

const TONE = { success: "var(--color-success)", danger: "var(--color-danger)", warning: "var(--color-warning)", accent: "var(--color-accent)", muted: "var(--color-text-muted)" } as const;

/**
 * Today's matchup card (concept C): the win-chance ring, "WK 10 · VS SHIESTY", both scores and a "trailing 27.2" chip, all
 * in one compact glass card. Tapping it expands the detail (the swing players on each side, with avatars) and a link to the
 * full Matchup page; it is the ONE place Today states the score and the win chance. Mobile twin:
 * components/TodayMatchupCard.tsx.
 */
export function TodayMatchupCard({ line, matchup, href }: { line: TeamStatusMatchup; matchup: MatchupResponse | null; href: string }) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const ring = todayMatchupRing(line);
  const swing =
    matchup?.my_team && matchup.opponent
      ? matchupSwingPlayers(swingInputsFromMatchup(matchup.my_team, matchup.opponent).inputs, matchup.opponent.team_name)
      : [];
  const status = statusRing(ring.pct, ring.pct != null ? `${ring.pct}%` : "–", ring.pct != null ? `Win chance ${ring.pct}%` : "Win chance not modeled", ring.tone === "muted" ? "muted" : ring.tone);
  return (
    <AccentCard accent="var(--color-accent-strong)" as="section" compact data-testid="today-matchup">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={bodyId}
        aria-label={[ring.kicker, ring.scoreLine, ring.chip?.label, status.label].filter(Boolean).join(". ")}
        className="flex w-full items-center gap-3 text-left"
        style={{ minHeight: 76, color: "inherit" }}
      >
        <StatusRingMark ring={status} size={68} />
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="break-words text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }} data-testid="today-matchup-kicker">
            {ring.kicker}
          </span>
          {ring.scoreLine ? (
            <span className="text-2xl font-extrabold tabular-nums leading-tight" data-testid="today-matchup-score">
              {ring.scoreLine}
            </span>
          ) : null}
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {ring.chip ? <ToneBadge label={ring.chip.label} color={TONE[ring.chip.tone]} testId="today-matchup-chip" /> : null}
            {ring.scoreCaption ? (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {ring.scoreCaption}
              </span>
            ) : null}
          </span>
        </span>
        <span aria-hidden="true" className="shrink-0 text-sm" style={{ color: "var(--color-text-muted)", transform: open ? "rotate(180deg)" : undefined }}>
          ⌄
        </span>
      </button>
      <Collapse open={open} id={bodyId}>
        <div className="flex flex-col gap-2 pt-1">
          <SwingPlayers swing={swing} />
          <Link href={href} className="tap-link self-start text-sm font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)", display: "inline-flex", alignItems: "center", textDecoration: "none" }}>
            Open matchup →
          </Link>
        </div>
      </Collapse>
    </AccentCard>
  );
}
