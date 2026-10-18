"use client";

import { useMemo, useState } from "react";

import type { DraftPickAsset, LeagueRankingsResponse, RankedPlayer } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PickRow } from "@/components/PickRow";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { groupPicksBySeason, visibleDraftPicks } from "@/lib/draftCenterPresentation";
import { waiverInjuryDisplay, formatWaiverScore } from "@/lib/waiversPresentation";
import {
  PLAYERS_AGE_FILTERS,
  PLAYERS_AVAILABILITY_FILTERS,
  PLAYERS_POSITION_FILTERS,
  PLAYERS_ROSTER_FILTERS,
  PLAYERS_STATUS_FILTERS,
  filterPlayers,
  type PlayersAgeFilter,
  type PlayersAvailabilityFilter,
  type PlayersRosterFilter,
  type PlayersStatusFilter,
} from "@/lib/playersPresentation";

/**
 * Players / Asset Explorer (Revision 16, extended in Revision 17) — ports
 * mobile's PlayersScreen.tsx, the named reference implementation: search by
 * name, filter by position/age/status/health, browse the full ranked
 * player pool for this league's active valuation lens (GET
 * .../leagues/{id}/rankings, the same endpoint GM Targets/Player Compare/
 * Trade Analyzer already read — see RankedPlayer's own docstring in
 * lib/api.ts calling this out as the shape a future Players page should
 * reuse rather than hand-roll a second one).
 *
 * Revision 16 deliberately left out two things modules/
 * player_asset_explorer_ui.py (the desktop Streamlit page this nav
 * destination used to open) has and mobile's screen doesn't: draft-pick
 * browsing and the rostered/available-in-this-league facet. Revision 17
 * adds both, now that the data exists on the web client (GET
 * .../draft-picks, already wired for Draft Center/Trade Analyzer; GET
 * .../rosters, already wired for Trade Analyzer's roster-browse) — no new
 * backend endpoint, just reusing what those pages already read:
 *  - A Players/Picks `PillRow` toggle (same control Draft Center's My
 *    Picks/League toggle and Trade Analyzer's asset-type toggle use).
 *  - Picks view: every draft-pick asset, grouped by season and rendered
 *    with the shared `PickRow` (see PickRow.tsx, extracted from
 *    DraftCenterContent.tsx so this doesn't invent a second row style).
 *    Always shows current owner — there's no "my picks" concept resolved
 *    on this page, and neither reference (desktop's pick_card_html nor
 *    Draft Center's PickRow) surfaces the original owner separately, so
 *    this doesn't either.
 *  - Players view: a roster-status facet (All/Rostered/Available) built
 *    from the union of every roster's `players` array — the same
 *    rostered_player_id_set the desktop module builds from
 *    roster_player_map, computed client-side from the same raw rosters
 *    endpoint Trade Analyzer's roster-browse already reads. Hidden
 *    entirely when that data isn't available, same as the desktop
 *    module's "League roster context unavailable" guard.
 *
 * Preview-capped the same way WaiversContent.tsx's All Free Agents board is
 * (a plain, non-virtualized list; mobile gets this for free from FlatList).
 */
const PREVIEW_ROWS = 60;

type PlayersView = "players" | "picks";

function PlayerRow({ player, leagueId, leagueName }: { player: RankedPlayer; leagueId: string; leagueName: string }) {
  const injury = waiverInjuryDisplay(player.injury_status);
  return (
    <div
      className="flex items-center justify-between gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentityTrigger
        identity={{ ...player, sourceLabel: "Players", leagueId, leagueName }}
        className="flex items-center gap-3 min-w-0"
      >
        <PositionBadge position={player.position} />
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={40} />
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
      </PlayerIdentityTrigger>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
          {formatWaiverScore(player.score)}
        </span>
        <OvrGauge rating={player.overall_rating ?? null} size="sm" />
        {player.position && player.position_rank ? (
          <span
            className="px-1.5 py-0.5 text-xs font-bold"
            style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
            title={`Ranked #${player.position_rank} among all ${player.position}s — overall, not just this league or your roster.`}
          >
            {player.position}
            {player.position_rank}
          </span>
        ) : null}
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
  picks = [],
  rosters = [],
}: {
  leagueId: string;
  leagueName: string;
  data: LeagueRankingsResponse;
  picks?: DraftPickAsset[];
  rosters?: Array<Record<string, unknown>>;
}) {
  const [view, setView] = useState<PlayersView>("players");
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("ALL");
  const [ageFilter, setAgeFilter] = useState<PlayersAgeFilter>("ALL");
  const [statusFilter, setStatusFilter] = useState<PlayersStatusFilter>("ALL");
  const [availabilityFilter, setAvailabilityFilter] = useState<PlayersAvailabilityFilter>("ALL");
  const [rosterFilter, setRosterFilter] = useState<PlayersRosterFilter>("ALL");

  // League-wide rostered player ids — the union of every roster's `players`
  // array (GET .../rosters, raw Sleeper passthrough). Same extraction
  // TradeAnalyzerContent.tsx's `otherTeams`/`myRosterIds` already do; empty
  // (never thrown) when the league has no roster data yet, which also hides
  // the facet below rather than showing a filter that can't do anything.
  const rosteredPlayerIds = useMemo(() => {
    const ids = new Set<string>();
    for (const roster of rosters) {
      const rosterPlayers = Array.isArray(roster.players) ? (roster.players as unknown[]) : [];
      for (const playerId of rosterPlayers) ids.add(String(playerId));
    }
    return ids;
  }, [rosters]);
  const rosterOwnershipKnown = rosters.length > 0;

  const filtered = useMemo(
    () =>
      filterPlayers(data.players, {
        search,
        position,
        ageFilter,
        statusFilter,
        availabilityFilter,
        rosterFilter,
        rosteredPlayerIds,
      }),
    [data.players, search, position, ageFilter, statusFilter, availabilityFilter, rosterFilter, rosteredPlayerIds],
  );
  const visible = filtered.slice(0, PREVIEW_ROWS);

  const pickSeasons = useMemo(() => groupPicksBySeason(visibleDraftPicks(picks, "league", "")), [picks]);

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Players
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {view === "players"
            ? "Ranked by value for this league's scoring, roster, and format settings. OVR percentiles a player against others at their position — tap Compare for the full breakdown."
            : "Every tracked draft-pick asset in this league, grouped by season."}
        </p>
      </header>

      {picks.length > 0 ? (
        <PillRow
          options={[
            { label: "Players", value: "players" },
            { label: "Picks", value: "picks" },
          ]}
          active={view}
          onSelect={(value) => setView(value as PlayersView)}
        />
      ) : null}

      {view === "players" ? (
        <>
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
            {rosterOwnershipKnown ? (
              <select
                value={rosterFilter}
                onChange={(event) => setRosterFilter(event.target.value as PlayersRosterFilter)}
                className="filter-select px-3 py-2 text-sm"
              >
                {PLAYERS_ROSTER_FILTERS.map((option) => (
                  <option key={option} value={option}>
                    {option === "ALL" ? "Any roster status" : option}
                  </option>
                ))}
              </select>
            ) : null}
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
        </>
      ) : pickSeasons.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No draft-pick assets are available for this league yet.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {pickSeasons.map(([season, seasonPicks]) => (
            <div key={season} className="flex flex-col gap-2">
              <span
                className="text-xs font-bold uppercase"
                style={{ color: "var(--color-text-secondary)", letterSpacing: "0.04em" }}
              >
                {season || "Future"}
              </span>
              <div
                style={{
                  background: "var(--color-surface-secondary)",
                  border: "var(--border-width-default) solid var(--color-border)",
                }}
              >
                {seasonPicks.map((pick, index) => (
                  <PickRow key={pick.pick_id} pick={pick} showOwner showDivider={index < seasonPicks.length - 1} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
