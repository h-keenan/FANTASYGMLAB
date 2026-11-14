"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { useExplorerLeague } from "@/context/ExplorerLeagueContext";
import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { api } from "@/lib/api";
import { trackUse } from "@/lib/analytics";
import { abbreviatePlayerName } from "@/lib/formatPlayerName";
import {
  addPin,
  assignMarkerLanes,
  binIndexAtPercentile,
  bucketPlayers,
  defaultComparison,
  explorerMetricsFor,
  formatExplorerDelta,
  formatExplorerValue,
  playersNearPercentile,
  poolMedian,
  rosterIdsFromRoster,
  searchExplorerPool,
  type ExplorerPlayer,
  type PercentileExplorerResponse,
} from "@/lib/percentileExplorer";
import { ordinal, statPercentileBand } from "@/lib/playerQuickViewPresentation";
import { PopupShell } from "@/components/PopupShell";
import { Tabs } from "@/components/Tabs";
import { percentileTabs } from "@/lib/sheetTabs";

const LANE_STEP = 74;
const BAR_H = 88;
const AXIS_H = 22;
const LIST_CAP = 30;

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
 * GET /v1/players/{id}/percentile-explorer?full=true). Explorable: switch
 * metric without closing, scrub or tap the histogram to list who sits in a
 * bucket, search any pool player onto the chart, mark your own roster, and a
 * pinned head-to-head summary. Every player label is first initial + full last
 * name (lib/formatPlayerName), never a character-truncated ellipsis. Rendered
 * in a portal so it stacks over the quick view; keyboard events stop here so
 * Esc closes only this sheet.
 */
export function PercentileExplorerSheet({
  playerId,
  statKey,
  statLabel,
  leagueId: leagueIdProp,
  onClose,
  onOpenPlayer,
}: {
  playerId: string;
  statKey: string;
  statLabel: string;
  /** When set, the user's rostered players are marked distinctly. */
  leagueId?: string | null;
  onClose: () => void;
  onOpenPlayer?: (player: ExplorerOpenPlayer) => void;
}) {
  const contextLeagueId = useExplorerLeague();
  const leagueId = leagueIdProp ?? contextLeagueId;
  const [metric, setMetric] = useState({ key: statKey, label: statLabel });
  const [pool, setPool] = useState<"position" | "all">("position");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [pins, setPins] = useState<string[]>([]);
  const [swapped, setSwapped] = useState(false);
  const [focusPct, setFocusPct] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [rosterIds, setRosterIds] = useState<Set<string>>(() => new Set());
  const scrubbing = useRef(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getPercentileExplorer(playerId, metric.key, pool, true)
      .then((data) => {
        if (cancelled) return;
        const known = new Set([...(data.pool_players ?? []), ...(data.nearby ?? [])].map((p) => p.player_id));
        const seeded = (data.nearby ?? []).map((p) => p.player_id);
        // Keep pins that still exist in this pool; top up with nearby players.
        setPins((prev) => {
          const kept = prev.filter((id) => known.has(id) && id !== playerId);
          return kept.length >= 3 ? kept : [...kept, ...seeded.filter((id) => !kept.includes(id))].slice(-7);
        });
        setState({ status: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [playerId, metric.key, pool]);

  useEffect(() => {
    if (!leagueId) return;
    let cancelled = false;
    api
      .getMyRoster(leagueId)
      .then((res) => {
        if (!cancelled && !res.reason) setRosterIds(rosterIdsFromRoster(res.roster));
      })
      .catch(() => {
        // Best-effort: no roster means no roster marks, never a guess.
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  useEffect(() => {
    trackUse("percentile_explorer", "opened", { props: { item_kind: statKey } });
    // once per sheet mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const data = state.status === "ready" ? state.data : null;
  const me = data?.player ?? null;
  const nearby = useMemo(() => data?.nearby ?? [], [data]);
  const poolPlayers = useMemo(() => data?.pool_players ?? (me ? [...nearby, me] : []), [data, me, nearby]);
  const hasFullPool = (data?.pool_players?.length ?? 0) > 0;
  const byId = useMemo(() => new Map(poolPlayers.map((p) => [p.player_id, p])), [poolPlayers]);
  const comparison = useMemo(() => {
    if (!me) return null;
    const picked = pickedId ? byId.get(pickedId) : null;
    return picked && picked.player_id !== me.player_id ? picked : defaultComparison(me, nearby);
  }, [me, nearby, pickedId, byId]);
  const markers = useMemo(() => {
    if (!me) return [];
    const ids = new Set(pins);
    if (comparison) ids.add(comparison.player_id);
    const others = [...ids].map((id) => byId.get(id)).filter((p): p is ExplorerPlayer => !!p && p.player_id !== me.player_id);
    return [...others, me].sort((a, b) => a.percentile - b.percentile);
  }, [me, pins, comparison, byId]);
  const lanes = useMemo(() => assignMarkerLanes(markers.map((m) => m.percentile)), [markers]);
  const laneCount = Math.max(1, ...lanes.map((lane) => lane + 1));
  const bins = useMemo(() => data?.bins ?? [], [data]);
  const maxCount = Math.max(1, ...bins.map((b) => b.count));
  const focusBin = focusPct == null ? -1 : binIndexAtPercentile(bins, focusPct);
  const bucket = useMemo(() => (hasFullPool && focusBin >= 0 ? bucketPlayers(poolPlayers, bins, focusBin) : []), [hasFullPool, focusBin, poolPlayers, bins]);
  const nearFocus = useMemo(
    () => (focusPct == null ? [] : playersNearPercentile(poolPlayers, focusPct, 1)),
    [focusPct, poolPlayers],
  );
  const results = useMemo(() => searchExplorerPool(poolPlayers, query), [poolPlayers, query]);
  const median = useMemo(() => poolMedian(poolPlayers), [poolPlayers]);
  const mine = useMemo(
    () => poolPlayers.filter((p) => rosterIds.has(p.player_id) && p.player_id !== me?.player_id),
    [poolPlayers, rosterIds, me],
  );
  const positionLabel = data?.position || "";
  const metrics = explorerMetricsFor(positionLabel || undefined, { key: statKey, label: statLabel });

  function changePool(next: string) {
    trackUse("percentile_explorer", "pool_changed", { props: { item_kind: metric.key, result: next === "all" ? "all" : "position" } });
    setPool(next === "all" ? "all" : "position");
    setState({ status: "loading" });
    setPickedId(null);
    setSwapped(false);
    setFocusPct(null);
  }

  function changeMetric(key: string) {
    const next = metrics.find((m) => m.key === key);
    if (!next || next.key === metric.key) return;
    trackUse("percentile_explorer", "metric_changed", { props: { item_kind: next.key } });
    setMetric(next);
    setState({ status: "loading" });
    setFocusPct(null);
    setSwapped(false);
  }

  function pick(player: ExplorerPlayer) {
    if (me && player.player_id === me.player_id) return;
    trackUse("percentile_explorer", "compare_picked", { props: { item_kind: metric.key } });
    setPickedId(player.player_id);
    setPins((prev) => addPin(prev, player.player_id));
    setSwapped(false);
    if (typeof navigator !== "undefined" && "vibrate" in navigator) navigator.vibrate?.(8);
  }

  function pctFromPointer(event: PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0) return null;
    return Math.min(100, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100));
  }

  function onScrubKey(event: KeyboardEvent<HTMLDivElement>) {
    const step = event.key === "ArrowRight" ? 2 : event.key === "ArrowLeft" ? -2 : 0;
    if (!step) return;
    event.preventDefault();
    setFocusPct((prev) => Math.min(100, Math.max(0, (prev ?? me?.percentile ?? 50) + step)));
  }

  const sheet = (
    <PopupShell title="Percentile explorer" onClose={onClose} labelledBy="pe-title" closeLabel="Close percentile explorer" backdropClassName="pe-backdrop" modalClassName="pe-sheet" portal={false}>
        <div className="pe-body">
          <h3 id="pe-title" className="pe-title">
            {metric.label} Percentile Explorer
          </h3>
          <p className="pe-hint">Drag across the chart or tap a bar to see who sits there.</p>

          <div className="pe-controls">
            <PillRow
              variant="scroll"
              ariaLabel="Metric"
              options={metrics.map((m) => ({ label: m.label, value: m.key }))}
              active={metric.key}
              onSelect={changeMetric}
            />
            <PillRow
              options={[
                { label: positionLabel ? `Same Position (${positionLabel})` : "Same Position", value: "position" },
                { label: "All Players", value: "all" },
              ]}
              active={pool}
              onSelect={changePool}
            />
          </div>

          {state.status === "loading" ? (
            <div className="pe-skeleton" data-testid="pe-loading" aria-busy="true" />
          ) : state.status === "error" ? (
            <EmptyState title="Couldn't load this stat" subtitle="Try again in a moment." />
          ) : data && data.reason === "" && me ? (
            <>
              <div className="pe-chart" data-testid="pe-chart" style={{ height: AXIS_H + BAR_H + 8 + laneCount * LANE_STEP }}>
                <div className="pe-bars" aria-hidden="true">
                  {bins.map((bin, index) => (
                    <span
                      key={index}
                      className={`pe-bar${index === focusBin ? " pe-bar--focus" : ""}`}
                      style={{
                        left: `${bin.pct_start}%`,
                        width: `${Math.max(0, bin.pct_end - bin.pct_start)}%`,
                        height: `${Math.max(3, (bin.count / maxCount) * 100)}%`,
                      }}
                    />
                  ))}
                  {focusPct != null ? <span className="pe-cursor" style={{ left: `${focusPct}%` }} /> : null}
                </div>
                <div
                  className="pe-scrub"
                  data-testid="pe-scrub"
                  role="slider"
                  tabIndex={0}
                  aria-label={`Scrub ${metric.label} percentile`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(focusPct ?? me.percentile)}
                  onKeyDown={onScrubKey}
                  onPointerDown={(event) => {
                    scrubbing.current = true;
                    event.currentTarget.setPointerCapture?.(event.pointerId);
                    const pct = pctFromPointer(event);
                    if (pct != null) setFocusPct(pct);
                  }}
                  onPointerMove={(event) => {
                    if (!scrubbing.current) return;
                    const pct = pctFromPointer(event);
                    if (pct != null) setFocusPct(pct);
                  }}
                  onPointerUp={() => {
                    scrubbing.current = false;
                  }}
                  onPointerCancel={() => {
                    scrubbing.current = false;
                  }}
                />
                {markers.map((marker, index) => {
                  const isMe = marker.player_id === me.player_id;
                  const isPicked = !isMe && comparison?.player_id === marker.player_id;
                  const isMine = !isMe && rosterIds.has(marker.player_id);
                  const left = Math.min(87, Math.max(13, marker.percentile));
                  const lift = lanes[index] * LANE_STEP;
                  const band = statPercentileBand(marker.percentile);
                  return (
                    <div key={marker.player_id}>
                      <span className="pe-stem" style={{ left: `${marker.percentile}%`, height: BAR_H + lift }} aria-hidden="true" />
                      <button
                        type="button"
                        className={`pe-marker${isMe ? " pe-marker--me" : ""}${isPicked ? " pe-marker--picked" : ""}${isMine ? " pe-marker--mine" : ""}`}
                        style={{ left: `${left}%`, bottom: AXIS_H + BAR_H + lift }}
                        aria-label={`${marker.name}, ${formatExplorerValue(marker.value, data.format)} ${metric.label}, ${ordinal(marker.percentile)} percentile`}
                        aria-pressed={isPicked}
                        disabled={isMe}
                        onClick={() => pick(marker)}
                      >
                        <span className="pe-marker-name">{abbreviatePlayerName(marker.name)}</span>
                        <PlayerFace player={marker} highlight={isMe} />
                        <span className="pe-marker-stat">
                          <span className="pe-marker-value">{formatExplorerValue(marker.value, data.format)}</span>
                          <span className={`pe-badge pe-badge--${band}`}>{ordinal(marker.percentile)}</span>
                          {isMine ? <span className="pe-mine-tag">MY</span> : null}
                        </span>
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
              <p className="pe-axis-title">{metric.label} percentile</p>
              {data.sample_note ? (
                <p className="pe-hint" data-testid="pe-sample-note">{data.sample_note}</p>
              ) : data.season ? (
                <p className="pe-hint">Season {data.season}</p>
              ) : null}
              {rosterIds.size > 0 && markers.some((m) => rosterIds.has(m.player_id) && m.player_id !== me.player_id) ? (
                <p className="pe-hint">MY = a player on your roster</p>
              ) : null}

              <Tabs
                id="percentile"
                ariaLabel="Percentile lists"
                tabs={percentileTabs({ hasFullPool, mineCount: mine.length }).map((tab) => ({
                  key: tab.key,
                  label: tab.label,
                  render: () =>
                    tab.key === "bucket" ? (
                focusBin < 0 ? (
                <p className="pe-hint">Drag across the chart or tap a bar to list the players in that bucket.</p>
                ) : (
                <section className="pe-bucket" data-testid="pe-bucket" aria-label="Players in this bucket">
                  <header className="pe-section-head">
                    <span>
                      {bins[focusBin].value_start === bins[focusBin].value_end
                        ? formatExplorerValue(bins[focusBin].value_start, data.format)
                        : `${formatExplorerValue(bins[focusBin].value_start, data.format)} to ${formatExplorerValue(bins[focusBin].value_end, data.format)}`}
                      {" · "}
                      {bucket.length} {bucket.length === 1 ? "player" : "players"}
                    </span>
                    {focusPct != null && nearFocus[0] ? <span>About the {ordinal(Math.round(focusPct))} percentile</span> : null}
                  </header>
                  {bucket.length === 0 ? (
                    <p className="pe-hint">Nobody sits in this bucket.</p>
                  ) : (
                    <PlayerList players={bucket.slice(0, LIST_CAP)} format={data.format} meId={me.player_id} comparisonId={comparison?.player_id} rosterIds={rosterIds} onPick={pick} />
                  )}
                  {bucket.length > LIST_CAP ? <p className="pe-hint">Showing the top {LIST_CAP}. Search to find anyone else.</p> : null}
                </section>
                )
                    ) : tab.key === "find" ? (
                <section className="pe-search" aria-label="Add a player to the chart">
                  <Input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={pool === "all" ? "Search any player to add" : `Search ${positionLabel || "position"} players to add`}
                    aria-label="Search players to add to the chart"
                    autoComplete="off"
                    className="pe-search-input"
                  />
                  {query.trim().length >= 2 ? (
                    results.length > 0 ? (
                      <PlayerList players={results} format={data.format} meId={me.player_id} comparisonId={comparison?.player_id} rosterIds={rosterIds} onPick={(player) => { pick(player); setQuery(""); }} />
                    ) : (
                      <p className="pe-hint">
                        No {pool === "all" ? "" : `${positionLabel || "position"} `}player with a ranked value matches that.
                        {pool === "position" ? " Try All Players." : ""}
                      </p>
                    )
                  ) : null}
                </section>
                    ) : (
                <section className="pe-mine" aria-label="Your roster">
                  <header className="pe-section-head">
                    <span>Your roster here</span>
                    <span>{mine.length}</span>
                  </header>
                  <PlayerList players={mine.slice(0, LIST_CAP)} format={data.format} meId={me.player_id} comparisonId={comparison?.player_id} rosterIds={rosterIds} onPick={pick} />
                </section>
                    ),
                }))}
              />
            </>
          ) : (
            <EmptyState {...explorerEmptyCopy(data?.reason ?? "no_data", positionLabel)} />
          )}
        </div>
        {data && data.reason === "" && me && comparison ? (
          <div className="pe-pinned">
            <CompareCard
              me={me}
              other={comparison}
              swapped={swapped}
              onSwap={() => setSwapped((value) => !value)}
              format={data.format}
              statLabel={metric.label}
              median={median}
              onOpenPlayer={onOpenPlayer}
            />
          </div>
        ) : null}
    </PopupShell>
  );

  return sheet;
}

function PlayerList({
  players,
  format,
  meId,
  comparisonId,
  rosterIds,
  onPick,
}: {
  players: ExplorerPlayer[];
  format: PercentileExplorerResponse["format"];
  meId: string;
  comparisonId?: string;
  rosterIds: Set<string>;
  onPick: (player: ExplorerPlayer) => void;
}) {
  return (
    <ul className="pe-list">
      {players.map((player) => {
        const isMe = player.player_id === meId;
        return (
          <li key={player.player_id}>
            <button
              type="button"
              className={`pe-row${player.player_id === comparisonId ? " pe-row--picked" : ""}`}
              disabled={isMe}
              onClick={() => onPick(player)}
              aria-label={`${isMe ? "Selected player " : "Compare with "}${player.name}`}
            >
              <PlayerAvatar playerId={player.player_id} size={32} />
              <span className="pe-row-id">
                <span className="pe-row-name">
                  {abbreviatePlayerName(player.name)}
                  {rosterIds.has(player.player_id) ? <span className="pe-mine-tag">MY ROSTER</span> : null}
                  {isMe ? <span className="pe-mine-tag">YOU</span> : null}
                </span>
                <span className="pe-row-meta">{[player.team, player.position].filter(Boolean).join(" · ")}</span>
              </span>
              <span className="pe-row-value">{formatExplorerValue(player.value, format)}</span>
              <span className={`pe-badge pe-badge--${statPercentileBand(player.percentile)}`}>{ordinal(player.percentile)}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function CompareCard({
  me,
  other,
  swapped,
  onSwap,
  format,
  statLabel,
  median,
  onOpenPlayer,
}: {
  me: ExplorerPlayer;
  other: ExplorerPlayer;
  swapped: boolean;
  onSwap: () => void;
  format: PercentileExplorerResponse["format"];
  statLabel: string;
  median: number | null;
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
        <span className="pe-side-name">{abbreviatePlayerName(player.name)}</span>
      </button>
      <span className="pe-side-meta">{[player.team, player.position].filter(Boolean).join(" · ")}</span>
      <span className="pe-side-stat">
        <span className="pe-side-value">{formatExplorerValue(player.value, format)}</span>
        <span className={`pe-badge pe-badge--${statPercentileBand(player.percentile)}`}>{ordinal(player.percentile)}</span>
      </span>
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
        {median != null ? (
          <span className="pe-delta-label" data-testid="pe-median">
            Pool median {formatExplorerValue(median, format)}
          </span>
        ) : null}
      </div>
      {side(right)}
    </div>
  );
}
