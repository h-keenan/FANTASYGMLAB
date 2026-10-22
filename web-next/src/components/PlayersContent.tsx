"use client";

import { EmptyState } from "@/components/EmptyState";
import { PlayerIdentity } from "@/components/PlayerRow";
import { ValueStat } from "@/components/ValueStat";
import { useMemo, useState } from "react";

import type { DraftPickAsset, LeagueRankingsResponse, RankedPlayer } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PickRow } from "@/components/PickRow";
import { PillRow } from "@/components/PillRow";
import { groupPicksBySeason, visibleDraftPicks } from "@/lib/draftCenterPresentation";
import { gamePlanTileHref } from "@/lib/gamePlanPresentation";
import { waiverInjuryDisplay, formatWaiverScore } from "@/lib/waiversPresentation";
import {
  OVERALL_RATING_SORT_KEY,
  PLAYERS_AGE_FILTERS,
  PLAYERS_AVAILABILITY_FILTERS,
  PLAYERS_POSITION_FILTERS,
  PLAYERS_ROSTER_FILTERS,
  PLAYERS_STATUS_FILTERS,
  VALUE_SORT_KEY,
  buildPlayersSortOptions,
  filterPlayers,
  findPlayersStat,
  formatPlayersPercentile,
  formatPlayersStatValue,
  sortPlayers,
  type PlayersAgeFilter,
  type PlayersAvailabilityFilter,
  type PlayersRosterFilter,
  type PlayersSortMode,
  type PlayersSortOption,
  type PlayersStatusFilter,
} from "@/lib/playersPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";

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
 *
 * Revision 20 (coridian_: "sort players by stats and also sort by
 * percentile of stats... a way when searching for players to quickly add
 * that player to a trade") adds two things:
 *  - Madden-style stat sort — Sort By (Value/OVR plus whatever
 *    position-relevant raw stats GET .../rankings now carries per player,
 *    see RankedPlayer.stats in lib/api.ts and
 *    modules.player_quick_view.rankings_stat_entries_for_row) with a
 *    Raw/Percentile toggle, built in lib/playersPresentation.ts's
 *    sortPlayers/buildPlayersSortOptions so this component stays pure
 *    rendering, same split as the filter predicates above.
 *  - An "Add to Trade" action per row, deep-linking to Trade Analyzer
 *    (the manual builder, not Trade Hub's AI ideas) with ?playerId= — same
 *    convention gamePlanTileHref already establishes for Waivers/Trade Hub,
 *    reused as-is rather than inventing a second deep-link shape.
 */
const PREVIEW_ROWS = 60;

type PlayersView = "players" | "picks";

/** The selected sort column's value for this player, Madden-style — hidden
 * entirely for the two baseline sort keys (Value/OVR already render their
 * own tile below) and for a stat this player simply has no value for (a
 * missing stat already sorts them to the bottom; showing nothing here is
 * the same fail-open choice, not a "—" that reads as broken). `sortMode`
 * picks raw value vs. this stat's own position-group percentile, matching
 * whatever the board is actually sorted by. */
function SortedStatTile({
  player,
  sortOption,
  sortMode,
}: {
  player: RankedPlayer;
  sortOption: PlayersSortOption;
  sortMode: PlayersSortMode;
}) {
  if (sortOption.key === VALUE_SORT_KEY || sortOption.key === OVERALL_RATING_SORT_KEY) return null;
  const stat = findPlayersStat(player, sortOption.key);
  if (!stat) return null;
  const display =
    sortMode === "percentile"
      ? stat.percentile != null
        ? formatPlayersPercentile(stat.percentile)
        : "—"
      : formatPlayersStatValue(stat);
  return (
    <div className="flex flex-col items-end gap-0.5">
      <span className="text-[0.625rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
        {stat.label}
        {sortMode === "percentile" ? " pct" : ""}
      </span>
      <span className="text-sm font-extrabold" style={{ color: "var(--color-text-secondary)" }}>
        {display}
      </span>
    </div>
  );
}

function PlayerRow({
  player,
  leagueId,
  leagueName,
  sortOption,
  sortMode,
}: {
  player: RankedPlayer;
  leagueId: string;
  leagueName: string;
  sortOption: PlayersSortOption;
  sortMode: PlayersSortMode;
}) {
  const injury = waiverInjuryDisplay(player.injury_status);
  return (
    <div
      className="flex items-center justify-between gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentity
        identity={{ ...player, sourceLabel: "Players", leagueId, leagueName }}
        playerId={player.player_id}
        name={player.name || `Player ${player.player_id}`}
        position={player.position}
        tier={player.tier}
        injuryStatus={injury.label}
      >
        {player.team || "—"}
      </PlayerIdentity>
      <div className="flex items-center gap-2 shrink-0">
        <SortedStatTile player={player} sortOption={sortOption} sortMode={sortMode} />
        {/* coridian_, 2026-10-19: "anywhere theres a value of a player it
            should say in small print value above it so its not glaring
            but its there in case someone gets confused" */}
        <ValueStat value={formatWaiverScore(player.score)} />
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
        {/* coridian_, 2026-10-20: "a way when searching for players to
            quickly add that player to a trade, where it inputs it into the
            trade hub into the appropriate section" — deep-links to Trade
            Analyzer (the manual send/receive builder, not Trade Hub's
            AI-suggested ideas) with ?playerId=, the same deep-link
            convention gamePlanTileHref already establishes for Waivers/
            Trade Hub. TradeAnalyzerContent reads it on mount, finds which
            roster owns this player, and pre-populates the builder — see
            that component's own docstring. */}
        <a
          href={gamePlanTileHref("trade-analyzer", leagueId, leagueName, player.player_id)}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-accent)", border: "var(--border-width-default) solid var(--color-accent)" }}
        >
          Add to Trade
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
  const [sortKey, setSortKey] = useState<string>(VALUE_SORT_KEY);
  const [sortMode, setSortMode] = useState<PlayersSortMode>("raw");

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
  // Sort-by options reflect whatever stats the currently-filtered pool
  // actually carries (e.g. a position filter narrows this to that
  // position's curated stat set) — see buildPlayersSortOptions. If the
  // user's chosen sortKey isn't among them (stale after changing the
  // position filter, or just the initial "value" default), fall back to
  // Value rather than erroring or silently sorting by nothing.
  const sortOptions = useMemo(() => buildPlayersSortOptions(filtered), [filtered]);
  const activeSortOption =
    sortOptions.find((option) => option.key === sortKey) ?? sortOptions[0];
  const sorted = useMemo(
    () => sortPlayers(filtered, activeSortOption.key, sortMode),
    [filtered, activeSortOption.key, sortMode],
  );
  const visible = sorted.slice(0, PREVIEW_ROWS);

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
            ? "Ranked by value for this league."
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

          {/* Madden-style stat sort (Revision 20): Sort By picks the column
              (Value/OVR, always present, plus whatever position-relevant
              raw stats the current filter's pool carries — see
              buildPlayersSortOptions), and the Raw/Percentile toggle picks
              whether a stat column sorts/displays its season total or its
              position-group percentile. The toggle only matters for a real
              stat column, so it's hidden for Value/OVR rather than shown
              disabled and confusing. */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
              Sort by
            </span>
            <select
              value={activeSortOption.key}
              onChange={(event) => setSortKey(event.target.value)}
              className="filter-select px-3 py-2 text-sm"
            >
              {sortOptions.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
            {activeSortOption.supportsPercentile ? (
              <PillRow
                options={[
                  { label: "Raw", value: "raw" },
                  { label: "Percentile", value: "percentile" },
                ]}
                active={sortMode}
                onSelect={(value) => setSortMode(value as PlayersSortMode)}
              />
            ) : null}
          </div>

          {visible.length === 0 ? (
            <EmptyState
              title="No players match"
              subtitle="Try a different search or filter."
              actionLabel="Clear filters"
              onAction={() => {
                setSearch("");
                setPosition("ALL");
                setAgeFilter("ALL");
                setStatusFilter("ALL");
                setAvailabilityFilter("ALL");
                setRosterFilter("ALL");
              }}
            />
          ) : (
            <div className="flex flex-col">
              {visible.map((player) => (
                <PlayerRow
                  key={player.player_id}
                  player={player}
                  leagueId={leagueId}
                  leagueName={leagueName}
                  sortOption={activeSortOption}
                  sortMode={sortMode}
                />
              ))}
            </div>
          )}
          {filtered.length > visible.length ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Showing the top {visible.length} of {filtered.length} matching players, sorted by {activeSortOption.label}
              {activeSortOption.supportsPercentile && sortMode === "percentile" ? " percentile" : ""}.
            </p>
          ) : (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {filtered.length} matching player{filtered.length === 1 ? "" : "s"}.
            </p>
          )}
        </>
      ) : pickSeasons.length === 0 ? (
        <EmptyState title="No draft-pick assets are available for this league yet." />
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
                className="glass-surface"
              >
                {seasonPicks.map((pick, index) => (
                  <PickRow key={pick.pick_id} pick={pick} showOwner showDivider={index < seasonPicks.length - 1} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      <ValuesCredit />
    </main>
  );
}
