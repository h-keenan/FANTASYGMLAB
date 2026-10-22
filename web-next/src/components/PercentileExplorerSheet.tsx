"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { SheetHandle } from "@/components/SheetHandle";
import { api } from "@/lib/api";
import { trackUse } from "@/lib/analytics";
import {
  assignMarkerLanes,
  defaultComparison,
  formatExplorerDelta,
  formatExplorerValue,
  type ExplorerPlayer,
  type PercentileExplorerResponse,
} from "@/lib/percentileExplorer";
import { ordinal, statPercentileBand } from "@/lib/playerQuickViewPresentation";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";

const LANE_COUNT = 3;
const LANE_STEP = 84;

export interface ExplorerOpenPlayer {
  player_id: string;
  name: string;
  team: string;
  position: string;
}

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: PercentileExplorerResponse };

/** Why there is no chart, in one line. Never a placeholder number. */
export function explorerEmptyCopy(reason: PercentileExplorerResponse["reason"], position?: string): { title: string; subtitle: string } {
  if (reason === "insufficient_pool") {
    return {
      title: "Not enough players to rank",
      subtitle: `Too few ${position || "position"} players have this stat for a trustworthy percentile.`,
    };
  }
  if (reason === "season_unavailable") {
    return { title: "Season not available", subtitle: "Only the current season is loaded." };
  }
  return { title: "No data for this stat", subtitle: "This player has no ranked value for it yet." };
}

function PlayerFace({ player, highlight }: { player: ExplorerPlayer; highlight: boolean }) {
  return (
    <span className={`pe-face${highlight ? " pe-face--me" : ""}`}>
      <PlayerAvatar playerId={player.player_id} size={highlight ? 36 : 30} />
    </span>
  );
}

/**
 * Percentile Explorer: bottom sheet behind one Player Quick View stat tile.
 * Same pool and percentile as the tile (served by
 * GET /v1/players/{id}/percentile-explorer), nearby real players as markers,
 * and a head-to-head compare card. Rendered in a portal so it stacks over the
 * quick view; keyboard events stop here so Esc closes only this sheet.
 */
export function PercentileExplorerSheet({
  playerId,
  statKey,
  statLabel,
  onClose,
  onOpenPlayer,
}: {
  playerId: string;
  statKey: string;
  statLabel: string;
  onClose: () => void;
  onOpenPlayer?: (player: ExplorerOpenPlayer) => void;
}) {
  const [pool, setPool] = useState<"position" | "all">("position");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [swapped, setSwapped] = useState(false);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const { sheetRef, sheetStyle } = useSheetDragDismiss({ onDismiss: onClose });

  useEffect(() => {
    let cancelled = false;
    api
      .getPercentileExplorer(playerId, statKey, pool)
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [playerId, statKey, pool]);

  useEffect(() => {
    closeRef.current?.focus();
    trackUse("percentile_explorer", "opened", { props: { item_kind: statKey } });
    // once per sheet mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const data = state.status === "ready" ? state.data : null;
  const me = data?.player ?? null;
  const nearby = useMemo(() => data?.nearby ?? [], [data]);
  const comparison = useMemo(() => {
    if (!me) return null;
    return nearby.find((p) => p.player_id === pickedId) ?? defaultComparison(me, nearby);
  }, [me, nearby, pickedId]);
  const markers = useMemo(() => {
    if (!me) return [];
    return [...nearby, me].sort((a, b) => a.percentile - b.percentile);
  }, [me, nearby]);
  const lanes = useMemo(() => assignMarkerLanes(markers.map((m) => m.percentile)), [markers]);
  const maxCount = Math.max(1, ...(data?.bins ?? []).map((b) => b.count));
  const positionLabel = data?.position || "";

  function changePool(next: string) {
    trackUse("percentile_explorer", "pool_changed", { props: { item_kind: statKey, result: next === "all" ? "all" : "position" } });
    setPool(next === "all" ? "all" : "position");
    setState({ status: "loading" });
    setPickedId(null);
    setSwapped(false);
  }

  const sheet = (
    <div
      className="pqv-backdrop pe-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.key === "Escape") onClose();
      }}
    >
      <div
        ref={sheetRef}
        className="pqv-modal pe-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pe-title"
        style={sheetStyle}
      >
        <SheetHandle />
        <button ref={closeRef} type="button" className="pqv-close" aria-label="Close percentile explorer" onClick={onClose}>
          ×
        </button>
        <div className="pe-body">
          <h3 id="pe-title" className="pe-title">
            {statLabel} Percentile Explorer
          </h3>
          <p className="pe-hint">Tap a player to compare where he sits.</p>

          <div className="pe-controls">
            <PillRow
              options={[
                { label: positionLabel ? `Same Position (${positionLabel})` : "Same Position", value: "position" },
                { label: "All Players", value: "all" },
              ]}
              active={pool}
              onSelect={changePool}
            />
            <PillRow options={[{ label: data?.season ? `Season ${data.season}` : "Season", value: "season" }]} active="season" onSelect={() => {}} />
          </div>

          {state.status === "loading" ? (
            <div className="pe-skeleton" data-testid="pe-loading" aria-busy="true" />
          ) : state.status === "error" ? (
            <EmptyState title="Couldn't load this stat" subtitle="Try again in a moment." />
          ) : data && data.reason === "" && me ? (
            <>
              <div className="pe-chart" data-testid="pe-chart" style={{ height: 86 + LANE_COUNT * LANE_STEP }}>
                <div className="pe-bars" aria-hidden="true">
                  {(data.bins ?? []).map((bin, index) => (
                    <span
                      key={index}
                      className="pe-bar"
                      style={{
                        left: `${bin.pct_start}%`,
                        width: `${Math.max(0, bin.pct_end - bin.pct_start)}%`,
                        height: `${(bin.count / maxCount) * 100}%`,
                      }}
                    />
                  ))}
                </div>
                {markers.map((marker, index) => {
                  const isMe = marker.player_id === me.player_id;
                  const isPicked = !isMe && comparison?.player_id === marker.player_id;
                  const left = Math.min(94, Math.max(6, marker.percentile));
                  const lift = lanes[index] * LANE_STEP;
                  const band = statPercentileBand(marker.percentile);
                  return (
                    <div key={marker.player_id}>
                      <span className="pe-stem" style={{ left: `${marker.percentile}%`, height: 64 + lift }} aria-hidden="true" />
                      <button
                        type="button"
                        className={`pe-marker${isMe ? " pe-marker--me" : ""}${isPicked ? " pe-marker--picked" : ""}`}
                        style={{ left: `${left}%`, bottom: 86 + lift }}
                        aria-label={`${marker.name}, ${formatExplorerValue(marker.value, data.format)} ${statLabel}, ${ordinal(marker.percentile)} percentile`}
                        aria-pressed={isPicked}
                        disabled={isMe}
                        onClick={() => {
                          trackUse("percentile_explorer", "compare_picked", { props: { item_kind: statKey } });
                          setPickedId(marker.player_id);
                          setSwapped(false);
                        }}
                      >
                        <span className="pe-marker-name">{marker.name}</span>
                        <span className="pe-marker-value">{formatExplorerValue(marker.value, data.format)}</span>
                        <PlayerFace player={marker} highlight={isMe} />
                        <span className={`pe-badge pe-badge--${band}`}>{ordinal(marker.percentile)}</span>
                      </button>
                    </div>
                  );
                })}
                <div className="pe-axis" aria-hidden="true">
                  {[0, 25, 50, 75, 100].map((tick) => (
                    <span key={tick} style={{ left: `${tick}%` }}>
                      {tick}
                    </span>
                  ))}
                </div>
              </div>
              <p className="pe-axis-title">{statLabel} percentile</p>

              {comparison ? (
                <CompareCard
                  me={me}
                  other={comparison}
                  swapped={swapped}
                  onSwap={() => setSwapped((value) => !value)}
                  format={data.format}
                  statLabel={statLabel}
                  onOpenPlayer={onOpenPlayer}
                />
              ) : null}
            </>
          ) : (
            <EmptyState {...explorerEmptyCopy(data?.reason ?? "no_data", positionLabel)} />
          )}
        </div>
      </div>
    </div>
  );

  return typeof document === "undefined" ? null : createPortal(sheet, document.body);
}

function CompareCard({
  me,
  other,
  swapped,
  onSwap,
  format,
  statLabel,
  onOpenPlayer,
}: {
  me: ExplorerPlayer;
  other: ExplorerPlayer;
  swapped: boolean;
  onSwap: () => void;
  format: PercentileExplorerResponse["format"];
  statLabel: string;
  onOpenPlayer?: (player: ExplorerOpenPlayer) => void;
}) {
  const left = swapped ? other : me;
  const right = swapped ? me : other;
  const delta = formatExplorerDelta(left.value, right.value, format);
  const side = (player: ExplorerPlayer) => (
    <div className="pe-side">
      <button
        type="button"
        className="pe-side-id"
        aria-label={`Open ${player.name}`}
        onClick={() =>
          onOpenPlayer?.({ player_id: player.player_id, name: player.name, team: player.team, position: player.position })
        }
      >
        <PlayerAvatar playerId={player.player_id} size={40} />
        <span className="pe-side-name">{player.name}</span>
      </button>
      <span className="pe-side-meta">{[player.team, player.position].filter(Boolean).join(" · ")}</span>
      <span className="pe-side-value">{formatExplorerValue(player.value, format)}</span>
      <span className={`pe-badge pe-badge--${statPercentileBand(player.percentile)}`}>{ordinal(player.percentile)} percentile</span>
    </div>
  );
  return (
    <div className="pe-compare" data-testid="pe-compare" aria-label={`${statLabel} comparison`}>
      {side(left)}
      <div className="pe-delta">
        <button type="button" className="pe-swap" aria-label="Swap comparison" onClick={onSwap}>
          ⇄
        </button>
        <span className="pe-delta-value">{delta}</span>
        <span className="pe-delta-label">vs comparison</span>
      </div>
      {side(right)}
    </div>
  );
}
