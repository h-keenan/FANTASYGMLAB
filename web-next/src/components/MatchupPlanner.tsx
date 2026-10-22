"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  api,
  type MatchupResponse,
  type MatchupStarter,
  type MatchupWhatIfCandidate,
  type MatchupWhatIfResponse,
  type MatchupWhatIfSlot,
} from "@/lib/api";
import { Button } from "@/components/Button";
import { PlayerRow } from "@/components/PlayerRow";
import { SheetHandle } from "@/components/SheetHandle";
import { ToneBadge } from "@/components/ToneBadge";
import {
  applySwap,
  blockedLabel,
  plannerBase,
  sleeperLeagueUrl,
  winPercent,
  type PlannerSource,
} from "@/lib/matchupPlanner";
import { slotDisplayLabel } from "@/lib/matchupPresentation";

/**
 * Lineup swap planner for Matchup. Planner only: FantasyDesk can't change a
 * Sleeper lineup, so the user makes the final change in Sleeper. All numbers
 * come from POST .../matchup/what-if, which scores the edited lineup with the
 * same win-probability function as the scoreboard.
 */

export interface PlannerState {
  source: PlannerSource;
  slots: MatchupWhatIfSlot[];
  starters: MatchupStarter[] | null;
  result: MatchupWhatIfResponse | null;
  /** Win percent of the lineup the user started from, to show the change. */
  baselinePct: number | null;
  busy: boolean;
  error: string | null;
}

export interface SheetState {
  index: number;
  data: NonNullable<MatchupWhatIfResponse["candidates"]> | null;
  error: string | null;
}

export function useLineupPlanner(leagueId: string, lens: string, matchup: MatchupResponse) {
  const [plan, setPlan] = useState<PlannerState | null>(null);
  const [sheet, setSheet] = useState<SheetState | null>(null);
  const counter = useRef(0);

  const evaluate = useCallback(
    async (slots: MatchupWhatIfSlot[], source: PlannerSource, baseline?: number | null) => {
      const ticket = ++counter.current;
      setPlan((current) => ({
        source,
        slots,
        starters: current?.starters ?? null,
        result: current?.result ?? null,
        baselinePct: baseline !== undefined ? baseline : (current?.baselinePct ?? null),
        busy: true,
        error: null,
      }));
      try {
        const result = await api.postMatchupWhatIf(leagueId, { lineup: slots, lens });
        if (ticket !== counter.current) return;
        setPlan((current) =>
          current
            ? {
                ...current,
                starters: result.lineup ?? current.starters,
                result,
                baselinePct:
                  baseline === undefined && current.baselinePct == null
                    ? winPercent(result.win_probability)
                    : current.baselinePct,
                busy: false,
              }
            : current,
        );
      } catch (err) {
        if (ticket !== counter.current) return;
        setPlan((current) =>
          current
            ? { ...current, busy: false, error: err instanceof Error ? err.message : "Couldn't update the lineup." }
            : current,
        );
      }
    },
    [leagueId, lens],
  );

  const start = useCallback(
    (source: PlannerSource) => {
      const base = plannerBase(matchup, source);
      if (!base) return;
      setSheet(null);
      setPlan({
        source,
        slots: base.slots,
        starters: base.players as MatchupStarter[],
        result: null,
        baselinePct: null,
        busy: true,
        error: null,
      });
      void evaluate(base.slots, source, undefined);
    },
    [matchup, evaluate],
  );

  const resetToSuggested = useCallback(() => {
    const base = plannerBase(matchup, "suggested");
    if (!base) return;
    setSheet(null);
    setPlan((current) => ({
      source: "suggested",
      slots: base.slots,
      starters: base.players as MatchupStarter[],
      result: current?.result ?? null,
      baselinePct: current?.baselinePct ?? null,
      busy: true,
      error: null,
    }));
    void evaluate(base.slots, "suggested");
  }, [matchup, evaluate]);

  const exit = useCallback(() => {
    counter.current += 1;
    setPlan(null);
    setSheet(null);
  }, []);

  const openSlot = useCallback(
    async (index: number) => {
      if (!plan) return;
      setSheet({ index, data: null, error: null });
      try {
        const result = await api.postMatchupWhatIf(leagueId, { lineup: plan.slots, edit_index: index, lens });
        setSheet((current) =>
          current && current.index === index ? { index, data: result.candidates ?? null, error: null } : current,
        );
      } catch (err) {
        setSheet({ index, data: null, error: err instanceof Error ? err.message : "Couldn't load options." });
      }
    },
    [plan, leagueId, lens],
  );

  const pick = useCallback(
    (candidate: MatchupWhatIfCandidate) => {
      if (!plan || !sheet || !candidate.selectable) return;
      const slots = applySwap(plan.slots, sheet.index, candidate);
      setSheet(null);
      void evaluate(slots, plan.source);
    },
    [plan, sheet, evaluate],
  );

  return { plan, sheet, start, resetToSuggested, exit, openSlot, pick, closeSheet: () => setSheet(null) };
}

const TONE_COLOR = {
  pro: "var(--color-success)",
  con: "var(--color-danger)",
  neutral: "var(--color-text-muted)",
} as const;

function Bullet({ tone, text }: { tone: keyof typeof TONE_COLOR; text: string }) {
  return (
    <li className="flex items-center gap-1.5 text-xs">
      <span
        aria-hidden="true"
        className="inline-block shrink-0"
        style={{ width: 6, height: 6, borderRadius: "50%", background: TONE_COLOR[tone] }}
      />
      <span style={{ color: tone === "neutral" ? "var(--color-text-muted)" : "var(--color-text-secondary)" }}>
        {text}
      </span>
    </li>
  );
}

function CandidateRow({ candidate, onPick }: { candidate: MatchupWhatIfCandidate; onPick: () => void }) {
  const { player } = candidate;
  const blocked = blockedLabel(candidate.blocked_reason);
  return (
    <li style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
      <button
        type="button"
        disabled={!candidate.selectable}
        onClick={onPick}
        className="w-full text-left py-2.5 flex flex-col gap-1.5"
        style={{ opacity: candidate.selectable ? 1 : 0.6, cursor: candidate.selectable ? "pointer" : "not-allowed" }}
      >
        <PlayerRow
          identity={null}
          playerId={player.player_id}
          name={player.name ?? "Unknown player"}
          position={player.position}
          tier={player.tier}
          injuryStatus={player.injury_label || null}
          disableQuickView
          className="py-0"
          trailing={
            blocked ? (
              <ToneBadge label={blocked} color="var(--color-warning)" />
            ) : candidate.points_delta != null ? (
              <span
                className="text-base font-extrabold tabular-nums"
                style={{
                  color:
                    Math.abs(candidate.points_delta) < 0.05
                      ? "var(--color-text-muted)"
                      : candidate.points_delta > 0
                        ? "var(--color-success)"
                        : "var(--color-danger)",
                }}
              >
                {candidate.points_delta > 0 ? "+" : candidate.points_delta < 0 ? "−" : ""}
                {Math.abs(candidate.points_delta).toFixed(1)}
              </span>
            ) : null
          }
        >
          {player.team || "FA"}
        </PlayerRow>
        {candidate.bullets.length ? (
          <ul className="flex flex-col gap-0.5 pl-1">
            {candidate.bullets.map((bullet) => (
              <Bullet key={bullet.text} tone={bullet.tone} text={bullet.text} />
            ))}
          </ul>
        ) : null}
      </button>
    </li>
  );
}

/** Eligible players for one slot, pros and cons each. Swipe down, Esc or the
 * backdrop closes it. */
export function SwapSheet({
  sheet,
  slot,
  onPick,
  onClose,
}: {
  sheet: SheetState;
  slot: string;
  onPick: (candidate: MatchupWhatIfCandidate) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const candidates = sheet.data?.candidates ?? [];
  return (
    <div
      className="pqv-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="pqv-modal" role="dialog" aria-modal="true" aria-labelledby="swap-sheet-title">
        <SheetHandle />
        <button type="button" className="pqv-close" aria-label="Close" onClick={onClose}>
          ×
        </button>
        <div className="pqv-scroll">
          <h2 id="swap-sheet-title" className="text-lg font-extrabold pr-10">
            {slotDisplayLabel(slot)} options
          </h2>
          {sheet.error ? (
            <p className="text-sm" style={{ color: "var(--color-danger)" }}>
              {sheet.error}
            </p>
          ) : !sheet.data ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Loading…
            </p>
          ) : sheet.data.slot_locked ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              This player&apos;s game has started, so the slot is locked.
            </p>
          ) : candidates.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              No one else on your roster can fill this slot.
            </p>
          ) : (
            <ul className="flex flex-col" aria-label="Eligible players">
              {candidates.map((candidate) => (
                <CandidateRow
                  key={candidate.player.player_id}
                  candidate={candidate}
                  onPick={() => onPick(candidate)}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

/** Controls above the lineup table: Edit lineup, or while editing the win
 * change, Reset to suggested, Open in Sleeper and Done. */
export function PlannerBar({
  editing,
  busy,
  error,
  baselinePct,
  currentPct,
  leagueId,
  onEdit,
  onReset,
  onDone,
}: {
  editing: boolean;
  busy: boolean;
  error: string | null;
  baselinePct: number | null;
  currentPct: number | null;
  leagueId: string;
  onEdit: () => void;
  onReset: () => void;
  onDone: () => void;
}) {
  if (!editing) {
    return (
      <Button variant="secondary" size="sm" onClick={onEdit}>
        Edit lineup
      </Button>
    );
  }
  const changed = baselinePct != null && currentPct != null && baselinePct !== currentPct;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 flex-wrap">
        <Button variant="secondary" size="sm" onClick={onReset} disabled={busy}>
          Reset to suggested
        </Button>
        <a
          href={sleeperLeagueUrl(leagueId)}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3 py-1.5 text-xs font-bold"
          style={{ color: "var(--color-accent)" }}
        >
          Open in Sleeper
        </a>
        <Button variant="ghost" size="sm" onClick={onDone} className="ml-auto">
          Done
        </Button>
      </div>
      {error ? (
        <p className="text-xs" style={{ color: "var(--color-danger)" }} role="alert">
          {error}
        </p>
      ) : changed ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Win probability {baselinePct}% to {currentPct}% with your edits.
        </p>
      ) : null}
    </div>
  );
}
