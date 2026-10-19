"use client";

import { useEffect, useState } from "react";

import { api, type ScheduleWeek } from "@/lib/api";

/**
 * Schedule tab (ports mobile's PlayerDetailScreen ScheduleSection,
 * mobile/src/screens/PlayerDetailScreen.tsx ~line 919) for the full Player
 * Profile page — the "PQV parity gap" (see PlayerQuickView.tsx's own header
 * doc comment and docs/roadmap.md). GET .../schedule is league-independent,
 * same endpoint mobile already calls.
 */

/** Tough defense = bad matchup for this player's offense (danger/red); weak
 * defense = good matchup (success/green); average or unranked (not enough
 * completed games yet) stays the normal text color. Never used for
 * anything but this display — see nfl_schedule.team_defense_strength's own
 * docstring for why this is real points-allowed data, not a per-player
 * grade. Byte-identical rule to mobile's defenseTierColor. */
function defenseTierColorVar(tier: ScheduleWeek["opponent_defense_tier"]): string {
  if (tier === "tough") return "var(--color-danger)";
  if (tier === "weak") return "var(--color-success)";
  return "var(--color-text-primary)";
}

/** The far-right projection slot for one schedule row —
 * modules.player_projections.project_player_week's output, already null on
 * the API for a played or bye week, so this only ever has something to say
 * for an upcoming game. Byte-identical rule to mobile's
 * scheduleProjectionDisplay. */
function scheduleProjectionDisplay(projection: ScheduleWeek["projection"]): { value: string | null; note: string | null } {
  if (!projection) return { value: null, note: null };
  if (projection.status === "ok" && projection.point_estimate != null) {
    return { value: projection.point_estimate.toFixed(1), note: null };
  }
  if (projection.status === "insufficient_player_data") return { value: null, note: "No projection yet" };
  if (projection.status === "no_opponent" || projection.status === "no_schedule_data") {
    return { value: null, note: "No projection yet" };
  }
  return { value: null, note: null };
}

function scheduleSpreadText(spreadLine: number | null): string | null {
  if (spreadLine == null) return null;
  if (spreadLine < 0) return `Favored by ${Math.abs(spreadLine).toFixed(1)}`;
  if (spreadLine > 0) return `Underdog by ${spreadLine.toFixed(1)}`;
  return "Even";
}

function ScheduleRow({ week }: { week: ScheduleWeek }) {
  const spreadText = scheduleSpreadText(week.spread_line);
  const projection = scheduleProjectionDisplay(week.projection);
  return (
    <div
      className="flex items-center justify-between gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <div className="text-xs font-bold" style={{ color: "var(--color-text-muted)", minWidth: "2.5rem" }}>
        WK {week.week}
      </div>
      <div className="flex flex-col min-w-0 flex-1">
        {week.bye ? (
          <span className="text-sm font-bold" style={{ color: "var(--color-text-muted)" }}>
            BYE
          </span>
        ) : (
          <span
            className="text-sm font-bold truncate"
            style={{ color: defenseTierColorVar(week.opponent_defense_tier) }}
          >
            {week.is_home ? "vs" : "@"} {week.opponent}
          </span>
        )}
        {week.bye ? null : week.played ? (
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            Final: {week.team_score != null ? Math.round(week.team_score) : "—"}-
            {week.opponent_score != null ? Math.round(week.opponent_score) : "—"}
          </span>
        ) : spreadText || week.total_line != null ? (
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {spreadText}
            {spreadText && week.total_line != null ? " · " : ""}
            {week.total_line != null ? `O/U ${week.total_line}` : ""}
          </span>
        ) : (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Line not posted yet
          </span>
        )}
      </div>
      {projection.value ? (
        <div className="flex flex-col items-end shrink-0">
          <span className="text-[0.625rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
            Proj
          </span>
          <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
            {projection.value}
          </span>
        </div>
      ) : projection.note ? (
        <span className="text-xs text-right shrink-0" style={{ color: "var(--color-text-muted)", maxWidth: "7rem" }}>
          {projection.note}
        </span>
      ) : null}
    </div>
  );
}

export function PlayerScheduleTab({ playerId }: { playerId: string }) {
  const [weeks, setWeeks] = useState<ScheduleWeek[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  // Which player `weeks`/`loadError` actually belong to — compared against
  // `playerId` below to derive "still loading" without a second setState
  // call synchronously at the top of the effect (React's
  // react-hooks/set-state-in-effect rule flags that pattern; see
  // PlayerCompareContent.tsx's own modelsLoadedFor comment for the same
  // reasoning this mirrors).
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    api
      .getPlayerSchedule(playerId)
      .then((result) => {
        if (cancelled) return;
        setWeeks(result.weeks);
        setLoadError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setWeeks(null);
        setLoadError(true);
      })
      .finally(() => {
        if (!cancelled) setLoadedFor(playerId);
      });

    return () => {
      cancelled = true;
    };
  }, [playerId]);

  if (loadedFor !== playerId) {
    return <p className="pqv-status-text">Loading schedule…</p>;
  }
  if (loadError) {
    return (
      <p className="pqv-status-text" role="alert">
        Couldn&apos;t load this player&apos;s schedule right now.
      </p>
    );
  }
  if (!weeks || weeks.length === 0) {
    return <p className="pqv-status-text">No schedule available for this player&apos;s team yet.</p>;
  }
  return (
    <div className="flex flex-col">
      <p className="text-xs mb-2" style={{ color: "var(--color-text-muted)" }}>
        Real opponent, market lines, and opponent defense strength (from actual points allowed) — never used to
        adjust this player&apos;s value or rankings.
      </p>
      {weeks.map((week) => (
        <ScheduleRow key={week.week} week={week} />
      ))}
    </div>
  );
}
