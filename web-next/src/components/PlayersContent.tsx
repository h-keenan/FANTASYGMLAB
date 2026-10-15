"use client";

import { useMemo, useState } from "react";

import type { LeagueRankingsResponse, RankedPlayer } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PositionBadge } from "@/components/PositionBadge";
import { waiverInjuryDisplay, formatWaiverScore } from "@/lib/waiversPresentation";
import {
  PLAYERS_AGE_FILTERS,
  PLAYERS_AVAILABILITY_FILTERS,
  PLAYERS_POSITION_FILTERS,
  PLAYERS_STATUS_FILTERS,
  filterPlayers,
  type PlayersAgeFilter,
  type PlayersAvailabilityFilter,
  type PlayersStatusFilter,
} from "@/lib/playersPresentation";

/**
 * Players / Asset Explorer (Revision 16) — ports mobile's PlayersScreen.tsx,
 * the named reference implementation: search by name, filter by position/
 * age/status/health, browse the full ranked player pool for this league's
 * active valuation lens (GET .../leagues/{id}/rankings, the same endpoint
 * GM Targets/Player Compare/Trade Analyzer already read — see RankedPlayer's
 * own docstring in lib/api.ts calling this out as the shape a future Players
 * page should reuse rather than hand-roll a second one).
 *
 * Deliberately NOT ported from modules/player_asset_explorer_ui.py (the
 * desktop Streamlit page this nav destination used to open): draft-pick
 * browsing ("Rookie picks"/"Future picks"/"All assets" asset-type scope) and
 * the rostered/available-in-this-league facet. Mobile's screen — the named
 * reference for this revision — has neither: it is a player-only list with
 * a health-based availability filter, not a roster-ownership one (that
 * meaning needs a league roster map GET .../rankings doesn't return). Adding
 * either would be inventing new product surface beyond what either client
 * ships today, not porting one.
 *
 * Preview-capped the same way WaiversContent.tsx's All Free Agents board is
 * (a plain, non-virtualized list; mobile gets this for free from FlatList).
 */
const PREVIEW_ROWS = 60;

function PlayerRow({ player, leagueId, leagueName }: { player: RankedPlayer; leagueId: string; leagueName: string }) {
  const injury = waiverInjuryDisplay(player.injury_status);
  return (
    <div
      className="flex items-center justify-between gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <div className="flex items-center gap-3 min-w-0">
        <PositionBadge position={player.position} />
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
              {player.name || `Player ${player.player_id}`}
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
            {player.team || "—"}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
          {formatWaiverScore(player.score)}
        </span>
        {player.position && player.position_rank ? (
          <span
            className="px-1.5 py-0.5 text-xs font-bold"
            style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
          >
            {player.position}
            {player.position_rank}
          </span>
        ) : null}
        <OvrGauge rating={player.overall_rating ?? null} size="sm" />
        <a
          href={`/player-compare/${encodeURIComponent(leagueId)}?a=${encodeURIComponent(player.player_id)}&name=${encodeURIComponent(leagueName)}`}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
        >
          Compare
        </a>
      </div>
    </div>
  );
}

export function PlayersContent({
  leagueId,
  leagueName,
  data,
}: {
  leagueId: string;
  leagueName: string;
  data: LeagueRankingsResponse;
}) {
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("ALL");
  const [ageFilter, setAgeFilter] = useState<PlayersAgeFilter>("ALL");
  const [statusFilter, setStatusFilter] = useState<PlayersStatusFilter>("ALL");
  const [availabilityFilter, setAvailabilityFilter] = useState<PlayersAvailabilityFilter>("ALL");

  const filtered = useMemo(
    () => filterPlayers(data.players, { search, position, ageFilter, statusFilter, availabilityFilter }),
    [data.players, search, position, ageFilter, statusFilter, availabilityFilter],
  );
  const visible = filtered.slice(0, PREVIEW_ROWS);

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Players
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Ranked by value for this league&apos;s scoring, roster, and format settings. OVR percentiles a player
          against others at their position — tap Compare for the full breakdown.
        </p>
      </header>

      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search players"
          className="filter-input px-3 py-2 text-sm flex-1 min-w-[10rem]"
        />
        <select
          value={position}
          onChange={(event) => setPosition(event.target.value)}
          className="filter-select px-3 py-2 text-sm"
        >
          {PLAYERS_POSITION_FILTERS.map((pos) => (
            <option key={pos} value={pos}>
              {pos}
            </option>
          ))}
        </select>
        <select
          value={ageFilter}
          onChange={(event) => setAgeFilter(event.target.value as PlayersAgeFilter)}
          className="filter-select px-3 py-2 text-sm"
        >
          {PLAYERS_AGE_FILTERS.map((option) => (
            <option key={option} value={option}>
              {option === "ALL" ? "Any age" : option}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as PlayersStatusFilter)}
          className="filter-select px-3 py-2 text-sm"
        >
          {PLAYERS_STATUS_FILTERS.map((option) => (
            <option key={option} value={option}>
              {option === "ALL" ? "Any status" : option}
            </option>
          ))}
        </select>
        <select
          value={availabilityFilter}
          onChange={(event) => setAvailabilityFilter(event.target.value as PlayersAvailabilityFilter)}
          className="filter-select px-3 py-2 text-sm"
        >
          {PLAYERS_AVAILABILITY_FILTERS.map((option) => (
            <option key={option} value={option}>
              {option === "ALL" ? "Any health" : option}
            </option>
          ))}
        </select>
      </div>

      {visible.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No players match this search and filter combination.
        </p>
      ) : (
        <div className="flex flex-col">
          {visible.map((player) => (
            <PlayerRow key={player.player_id} player={player} leagueId={leagueId} leagueName={leagueName} />
          ))}
        </div>
      )}
      {filtered.length > visible.length ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Showing the top {visible.length} of {filtered.length} matching players, ranked by current value.
        </p>
      ) : (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {filtered.length} matching player{filtered.length === 1 ? "" : "s"}.
        </p>
      )}
    </main>
  );
}
