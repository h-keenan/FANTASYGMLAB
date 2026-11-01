"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { trackFeatureUse } from "@/lib/analytics";
import { gamePlanTileHref } from "@/lib/gamePlanPresentation";
import { rosterOwnershipFrom, tradeShortcutsFor, type RosterOwnership } from "@/lib/tradeShortcuts";

/**
 * The contextual trade actions on Player Quick View and the Player Profile
 * page (tap-depth audit 2026-10, proposals 1, 2 and 7):
 *
 * - "Add to Trade" (every player): Trade Analyzer with this player
 *   pre-filled on the right side, the owning team selected, and the empty
 *   side focused. Same ?playerId= deep link the Players list already uses.
 * - "Find trades" (players on my roster): Trade Finder with this player
 *   selected and the search already run. Trade Finder's own Premium gate
 *   applies, exactly as for a manual search.
 * - "Add to GM Targets" (players not on my roster): the same watch toggle
 *   as mobile's Player Detail (☆ Add / ★ Watching), on the existing GM
 *   Targets endpoints, with the same "GM Targets is full" message.
 *
 * Ownership comes from GET .../my-roster plus .../rosters (the same pair
 * mobile's useRosterOwnership reads). Until it answers, or if my-roster fails,
 * nothing shows: never a button on a guess. A failed /rosters degrades to
 * "my players only". `hideAddToTrade` is for a quick view opened inside the
 * Trade Analyzer itself.
 * Rendered inside the caller's existing `.pqv-actions` row.
 */
export function PlayerLeagueActions({
  leagueId,
  leagueName,
  playerId,
  sourceSurface,
  hideAddToTrade = false,
}: {
  leagueId: string;
  leagueName: string;
  playerId: string;
  /** GM Targets provenance, e.g. "player_quick_view" (mobile sends
   * "player_detail"). */
  sourceSurface: string;
  hideAddToTrade?: boolean;
}) {
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [ownership, setOwnership] = useState<RosterOwnership | null>(null);
  const [onMyRoster, setOnMyRoster] = useState<boolean | null>(null);
  const [watching, setWatching] = useState<boolean | null>(null);
  const [watchBusy, setWatchBusy] = useState(false);
  const [watchMessage, setWatchMessage] = useState<string | null>(null);
  const key = `${leagueId}:${playerId}`;

  useEffect(() => {
    let cancelled = false;
    // Promise.resolve().then(...) so a synchronous throw from the API layer
    // is a rejection here, never a crash of the whole sheet.
    Promise.resolve()
      .then(() =>
        Promise.all([
          api.getMyRoster(leagueId),
          Promise.resolve()
            .then(() => api.getLeagueRosters(leagueId))
            .catch(() => null),
        ]),
      )
      .then(async ([result, rostersResult]) => {
        if (cancelled) return;
        const players = Array.isArray(result?.roster?.players) ? (result.roster!.players as unknown[]) : [];
        const mine = players.map(String).includes(playerId);
        if (!result?.ok && players.length === 0) {
          setLoadedFor(key);
          return;
        }
        setOnMyRoster(mine);
        setOwnership(rosterOwnershipFrom(result.roster ?? null, rostersResult?.rosters ?? []));
        if (!mine) {
          try {
            const targets = await api.getGmTargets(leagueId);
            if (!cancelled) setWatching(targets.targets.some((target) => target.player_id === playerId));
          } catch {
            if (!cancelled) setWatching(null);
          }
        }
        if (!cancelled) setLoadedFor(key);
      })
      .catch(() => {
        if (!cancelled) setLoadedFor(key);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, playerId, key]);

  async function toggleWatch() {
    if (watching === null || watchBusy) return;
    setWatchBusy(true);
    setWatchMessage(null);
    try {
      if (watching) {
        await api.removeGmTarget(leagueId, playerId);
        setWatching(false);
      } else {
        const result = await api.addGmTarget(leagueId, playerId, sourceSurface);
        if (result.ok) {
          setWatching(true);
        } else if (result.reason === "at_cap") {
          setWatchMessage(
            `GM Targets is full (${result.cap ?? "limit reached"}). Remove a target before adding another.`,
          );
        } else {
          setWatchMessage("Could not update GM Targets. Please try again in a moment.");
        }
      }
    } catch {
      setWatchMessage("Could not update GM Targets. Please try again in a moment.");
    } finally {
      setWatchBusy(false);
    }
  }

  const ready = loadedFor === key;
  const shortcuts = ready ? tradeShortcutsFor(playerId, ownership) : { canAddToTrade: false, canFindTrades: false };

  return (
    <>
      {shortcuts.canAddToTrade && !hideAddToTrade ? (
        <a
          className="pqv-action-link pqv-action-link--primary"
          href={gamePlanTileHref("trade-analyzer", leagueId, leagueName, playerId)}
          onClick={() => trackFeatureUse("pqv_add_to_trade", { leagueId, dedupe: false })}
        >
          Add to Trade
        </a>
      ) : null}
      {ready && shortcuts.canFindTrades ? (
        <a
          className="pqv-action-link pqv-action-link--primary"
          href={gamePlanTileHref("trade-finder", leagueId, leagueName, playerId)}
          onClick={() => trackFeatureUse("pqv_find_trades", { leagueId, dedupe: false })}
        >
          Find trades
        </a>
      ) : null}
      {ready && onMyRoster === false && watching !== null ? (
        <button
          type="button"
          className={`pqv-action-link${watching ? " pqv-action-link--active" : ""}`}
          onClick={() => void toggleWatch()}
          disabled={watchBusy}
          aria-pressed={watching}
        >
          {watching ? "★ Watching" : "☆ Add to GM Targets"}
        </button>
      ) : null}
      {watchMessage ? (
        <p className="pqv-action-message" role="status">
          {watchMessage}
        </p>
      ) : null}
    </>
  );
}
