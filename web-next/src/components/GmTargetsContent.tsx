"use client";

import { useMemo, useState } from "react";

import type { GmTarget, GmTargetsResponse, LeagueRankingsResponse } from "@/lib/api";
import { api } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PositionBadge } from "@/components/PositionBadge";
import { destinationCtaLabel } from "@/lib/streamlitLink";
import { formatWaiverScore, waiverInjuryDisplay } from "@/lib/waiversPresentation";
import { groupTargetRows, targetContextLine, type GmTargetRow } from "@/lib/gmTargetsPresentation";

/**
 * Ports mobile's GmTargetsScreen.tsx for Revision 11 — the GM_TOOLS nav
 * destination that tracks players a user is considering buying, selling,
 * adding, or monitoring (distinct from the general Waivers board). Reads
 * the exact same GET .../gm-targets preference rows mobile's screen reads,
 * joined client-side against GET .../rankings for display (name/position/
 * team/score/rank/injury) — the same join mobile already does, no new
 * enrichment logic written here. See modules/gm_targets.py for the real
 * source of truth (untouchable flag, caps, the durable table itself).
 *
 * Deliberately NOT ported: Streamlit's richer per-card "canonical action" /
 * "material change" / ownership-status lines and the Waivers/Trade Hub
 * workflow handoff button. Those read from session-state-shaped surfaces
 * (modules.canonical_recommendation_narrative, modules.decision_change_
 * history) that have no stateless API equivalent today, and mobile's own
 * reference screen — the one named reference implementation for this
 * revision — doesn't show them either. Also NOT ported: adding a target
 * from this page. Both clients only ever add from a player
 * detail/quick-view surface, neither of which has a Next.js page yet; this
 * page is read/manage-only (toggle untouchable, remove), same as mobile.
 */

function TargetRowView({
  row,
  leagueId,
  leagueName,
  onToggleUntouchable,
  onRemove,
}: {
  row: GmTargetRow;
  leagueId: string;
  leagueName: string;
  onToggleUntouchable: (playerId: string, next: boolean) => void;
  onRemove: (playerId: string) => void;
}) {
  const { target, player } = row;
  const injury = waiverInjuryDisplay(player?.injury_status);
  const contextLine = targetContextLine(row);
  const name = player?.name || `Player ${target.player_id}`;

  return (
    <div className="flex flex-col gap-2 py-3" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <PositionBadge position={player?.position} />
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
                {name}
              </span>
              {injury.label ? (
                <span
                  className="text-xs font-bold uppercase"
                  style={{
                    color:
                      injury.tone === "danger"
                        ? "var(--color-danger)"
                        : injury.tone === "warning"
                          ? "var(--color-warning)"
                          : "var(--color-text-muted)",
                  }}
                >
                  {injury.label}
                </span>
              ) : null}
            </div>
            <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
              {player?.team || "—"}
              {contextLine ? ` · ${contextLine}` : ""}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {player?.score !== null && player?.score !== undefined ? (
            <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
              {formatWaiverScore(player.score)}
            </span>
          ) : null}
          {player?.position_rank ? (
            <span
              className="px-1.5 py-0.5 text-xs font-bold"
              style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
            >
              {player.position}
              {player.position_rank}
            </span>
          ) : null}
          <OvrGauge rating={player?.overall_rating ?? null} size="sm" />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <a
          href={`/player-compare/${encodeURIComponent(leagueId)}?a=${encodeURIComponent(target.player_id)}&name=${encodeURIComponent(leagueName)}`}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
        >
          Compare
        </a>
        <button
          type="button"
          onClick={() => onToggleUntouchable(target.player_id, !target.untouchable)}
          className="px-2 py-1 text-xs font-bold"
          style={
            target.untouchable
              ? { background: "var(--color-premium)", color: "var(--color-brand-mark-ink)", border: "var(--border-width-default) solid var(--color-premium)" }
              : { color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }
          }
        >
          {target.untouchable ? "Unmark untouchable" : "Mark untouchable"}
        </button>
        <button
          type="button"
          onClick={() => onRemove(target.player_id)}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-danger)", border: "var(--border-width-default) solid var(--color-danger)" }}
        >
          Remove
        </button>
      </div>
    </div>
  );
}

function TargetGroup({
  title,
  caption,
  rows,
  leagueId,
  leagueName,
  onToggleUntouchable,
  onRemove,
}: {
  title: string;
  caption: string;
  rows: GmTargetRow[];
  leagueId: string;
  leagueName: string;
  onToggleUntouchable: (playerId: string, next: boolean) => void;
  onRemove: (playerId: string) => void;
}) {
  if (rows.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <h2 style={{ font: "var(--type-section-title)" }}>{title}</h2>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {caption}
      </p>
      <div
        className="flex flex-col px-3"
        style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
      >
        {rows.map((row) => (
          <TargetRowView
            key={row.target.player_id}
            row={row}
            leagueId={leagueId}
            leagueName={leagueName}
            onToggleUntouchable={onToggleUntouchable}
            onRemove={onRemove}
          />
        ))}
      </div>
    </section>
  );
}

export function GmTargetsContent({
  leagueId,
  leagueName,
  targets,
  rankings,
}: {
  leagueId: string;
  leagueName: string;
  targets: GmTargetsResponse;
  rankings: LeagueRankingsResponse;
}) {
  const [rows, setRows] = useState<GmTarget[]>(targets.targets);

  const byId = useMemo(() => new Map(rankings.players.map((p) => [p.player_id, p])), [rankings.players]);
  const joined = useMemo<GmTargetRow[]>(
    () => rows.map((target) => ({ target, player: byId.get(target.player_id) ?? null })),
    [rows, byId],
  );
  const { untouchable, watching } = useMemo(() => groupTargetRows(joined), [joined]);

  const toggleUntouchable = (playerId: string, next: boolean) => {
    setRows((prev) => prev.map((row) => (row.player_id === playerId ? { ...row, untouchable: next } : row)));
    api
      .setGmTargetUntouchable(leagueId, playerId, next)
      .then((result) => {
        if (!result.ok) {
          setRows((prev) => prev.map((row) => (row.player_id === playerId ? { ...row, untouchable: !next } : row)));
        }
      })
      .catch(() => {
        setRows((prev) => prev.map((row) => (row.player_id === playerId ? { ...row, untouchable: !next } : row)));
      });
  };

  const removeTarget = (playerId: string) => {
    const previous = rows;
    setRows((prev) => prev.filter((row) => row.player_id !== playerId));
    api.removeGmTarget(leagueId, playerId).catch(() => {
      setRows(previous);
    });
  };

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          GM Targets
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Keep an eye on players you&apos;re considering buying, selling, adding, or monitoring.
        </p>
      </header>

      {joined.length === 0 ? (
        <div className="flex flex-col gap-3 items-start">
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No GM Targets yet. Add players you&apos;re considering from a player&apos;s profile to start watching them.
          </p>
          <a
            href={`/players/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`}
            className="text-sm font-bold"
            style={{ color: "var(--color-accent)" }}
          >
            {destinationCtaLabel("players")} →
          </a>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          <TargetGroup
            title="Untouchable"
            caption="Kept out of auto-generated trade suggestions."
            rows={untouchable}
            leagueId={leagueId}
            leagueName={leagueName}
            onToggleUntouchable={toggleUntouchable}
            onRemove={removeTarget}
          />
          <TargetGroup
            title="Watching"
            caption="Tracked here — no trade protection applied."
            rows={watching}
            leagueId={leagueId}
            leagueName={leagueName}
            onToggleUntouchable={toggleUntouchable}
            onRemove={removeTarget}
          />
        </div>
      )}
    </main>
  );
}
