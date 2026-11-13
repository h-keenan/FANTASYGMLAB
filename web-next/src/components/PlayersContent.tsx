"use client";

import { PositionBadge } from "@/components/PositionBadge";
import { EmptyState } from "@/components/EmptyState";
import { PlayerIdentity } from "@/components/PlayerRow";
import { ValueStat } from "@/components/ValueStat";
import { useMemo, useState } from "react";
import { mergeSearchMatches, useLeaguePlayerSearch } from "@/lib/leaguePlayerSearch";

import type { DraftPickAsset, LeagueIdpValuesResponse, LeagueRankingsResponse, RankedPlayer } from "@/lib/api";
import {
  IDP_CONFIDENCE_LABEL,
  idpMethodNote,
  idpRowsAsRankedPlayers,
  isIdpPositionFilter,
  playersPositionOptions,
} from "@/lib/idpPresentation";
import { OvrGauge } from "@/components/OvrGauge";
import { PickRow, draftPickRowProps } from "@/components/PickRow";
import { PillRow } from "@/components/PillRow";
import { FilterSheet } from "@/components/ui/FilterSheet";
import { singleValue, valuesFromSingles, type FilterGroup, type FilterValues } from "@/lib/filterSheet";
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
import { PageTitle } from "@/components/PageTitle";

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
      <span className="text-[0.6875rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
        {stat.label}
        {sortMode === "percentile" ? " pct" : ""}
      </span>
      <span className="text-sm font-extrabold" style={{ color: "var(--color-text-secondary)" }}>
        {display}
      </span>
    </div>
  );
}

/** Icon-only row actions (compare / add to trade): labelled via aria-label + title on the link. */
function RowActionGlyph({ name }: { name: "compare" | "trade" }) {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {name === "compare" ? (
        <>
          <path d="M8 4v16M4 8l4-4 4 4" />
          <path d="M16 20V4M12 16l4 4 4-4" />
        </>
      ) : (
        <>
          <path d="M4 8h13M13 4l4 4-4 4" />
          <path d="M20 16H7M11 12l-4 4 4 4" />
        </>
      )}
    </svg>
  );
}

function PlayerRow({
  player,
  leagueId,
  leagueName,
  sortOption,
  sortMode,
  idpConfidence,
}: {
  player: RankedPlayer;
  leagueId: string;
  leagueName: string;
  sortOption: PlayersSortOption;
  sortMode: PlayersSortMode;
  /** Set only for IDP rows: they show their projection basis instead of a
   * rank/OVR, and skip Compare / Add to Trade (those engines do not value
   * defenders yet). */
  idpConfidence?: string;
}) {
  const injury = waiverInjuryDisplay(player.injury_status);
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-x-3 gap-y-3 py-3"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentity
        identity={{ ...player, sourceLabel: "Players", leagueId, leagueName }}
        playerId={player.player_id}
        name={player.name || `Player ${player.player_id}`}
        position={player.position}
        tier={player.tier}
        injuryStatus={injury.label}
        className="flex-1 basis-full sm:basis-48 min-w-0"
      >
        {player.team || "—"}
      </PlayerIdentity>
      <div className="flex flex-wrap items-center gap-2 min-w-0 max-w-full">
        <SortedStatTile player={player} sortOption={sortOption} sortMode={sortMode} />
        {/* coridian_, 2026-10-19: "anywhere theres a value of a player it
            should say in small print value above it so its not glaring
            but its there in case someone gets confused" */}
        <ValueStat value={formatWaiverScore(player.score)} />
        {idpConfidence ? (
          <span
            className="px-1.5 py-0.5 text-xs font-bold"
            style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
            title="How much real defensive play the projection rests on."
          >
            {IDP_CONFIDENCE_LABEL[idpConfidence] ?? idpConfidence}
          </span>
        ) : (
          <OvrGauge rating={player.overall_rating ?? null} size="sm" />
        )}
        {player.position && player.position_rank ? (
          <PositionBadge position={player.position} rank={player.position_rank} title={`Ranked #${player.position_rank} among all ${player.position}s — overall, not just this league or your roster.`} />
        ) : null}
        {idpConfidence ? null : (
          <a
            href={`/player-compare/${encodeURIComponent(leagueId)}?a=${encodeURIComponent(player.player_id)}&name=${encodeURIComponent(leagueName)}`}
            aria-label="Compare"
            title="Compare"
            className="inline-flex items-center justify-center min-h-[var(--touch-target-min)] min-w-[var(--touch-target-min)]"
            style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)", borderRadius: "var(--radius-control)" }}
          >
            <RowActionGlyph name="compare" />
          </a>
        )}
        {/* coridian_, 2026-10-20: "a way when searching for players to
            quickly add that player to a trade, where it inputs it into the
            trade hub into the appropriate section" — deep-links to Trade
            Analyzer (the manual send/receive builder, not Trade Hub's
            AI-suggested ideas) with ?playerId=, the same deep-link
            convention gamePlanTileHref already establishes for Waivers/
            Trade Hub. TradeAnalyzerContent reads it on mount, finds which
            roster owns this player, and pre-populates the builder — see
            that component's own docstring. */}
        {idpConfidence ? null : (
          <a
            href={gamePlanTileHref("trade-analyzer", leagueId, leagueName, player.player_id)}
            aria-label="Add to Trade"
            title="Add to Trade"
            className="inline-flex items-center justify-center min-h-[var(--touch-target-min)] min-w-[var(--touch-target-min)]"
            style={{
              color: "var(--color-accent)",
              border: "var(--border-width-default) solid var(--color-accent)",
              borderRadius: "var(--radius-control)",
              background: "color-mix(in srgb, var(--color-accent) 12%, transparent)",
            }}
          >
            <RowActionGlyph name="trade" />
          </a>
        )}
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
  idp = null,
  lens = "Dynasty",
}: {
  leagueId: string;
  leagueName: string;
  data: LeagueRankingsResponse;
  picks?: DraftPickAsset[];
  rosters?: Array<Record<string, unknown>>;
  /** IDP leagues only (see lib/idpPresentation.ts); null/`idp: false` leaves
   * this page exactly as it is for every other league. */
  idp?: LeagueIdpValuesResponse | null;
  /** Valuation lens the `data` rankings were fetched under; used for name search. */
  lens?: string;
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

  // Defender rows, adapted to RankedPlayer so the shared filter/sort/row code
  // applies. They are only the pool when a DL/LB/DB chip is selected, so the
  // offensive board (and its ranks) never mixes with a different scale.
  const idpPlayers = useMemo(() => idpRowsAsRankedPlayers(idp), [idp]);
  const idpConfidenceById = useMemo(() => {
    const map = new Map<string, string>();
    for (const row of idp?.players ?? []) map.set(row.player_id, row.confidence);
    return map;
  }, [idp]);
  const positionOptions = useMemo(() => playersPositionOptions(PLAYERS_POSITION_FILTERS, idp), [idp]);
  const idpSelected = idpPlayers.length > 0 && isIdpPositionFilter(position);
  // The rankings window is the top 300; search also asks the server so a lower-ranked
  // player (e.g. a rookie backup) is still found rather than silently absent.
  const searchMatches = useLeaguePlayerSearch(leagueId, lens, search);
  const windowPool = data.players;
  const offensePool = useMemo(() => mergeSearchMatches(windowPool, searchMatches), [windowPool, searchMatches]);
  const pool = idpSelected ? idpPlayers : offensePool;

  const filtered = useMemo(
    () =>
      filterPlayers(pool, {
        search,
        position,
        ageFilter,
        statusFilter,
        availabilityFilter,
        rosterFilter,
        rosteredPlayerIds,
      }),
    [pool, search, position, ageFilter, statusFilter, availabilityFilter, rosterFilter, rosteredPlayerIds],
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

  // One Filters button instead of five selects (FilterSheet): the same five
  // facets, committed together with Apply.
  const filterGroups = useMemo<FilterGroup[]>(
    () => [
      { id: "position", label: "Position", anyValue: "ALL", hidden: true, options: positionOptions.map((pos) => ({ value: pos, label: pos === "ALL" ? "Any" : pos })) },
      { id: "age", label: "Age", anyValue: "ALL", options: PLAYERS_AGE_FILTERS.map((option) => ({ value: option, label: option === "ALL" ? "Any age" : option })) },
      { id: "status", label: "Status", anyValue: "ALL", options: PLAYERS_STATUS_FILTERS.map((option) => ({ value: option, label: option === "ALL" ? "Any status" : option })) },
      { id: "health", label: "Health", anyValue: "ALL", options: PLAYERS_AVAILABILITY_FILTERS.map((option) => ({ value: option, label: option === "ALL" ? "Any health" : option })) },
      { id: "roster", label: "Roster", anyValue: "ALL", hidden: !rosterOwnershipKnown, options: PLAYERS_ROSTER_FILTERS.map((option) => ({ value: option, label: option === "ALL" ? "Any roster status" : option })) },
    ],
    [positionOptions, rosterOwnershipKnown],
  );
  const filterValues = useMemo(
    () => valuesFromSingles(filterGroups, { position, age: ageFilter, status: statusFilter, health: availabilityFilter, roster: rosterFilter }),
    [filterGroups, position, ageFilter, statusFilter, availabilityFilter, rosterFilter],
  );
  // How many players a draft selection would show, so Apply can say "Show 24 results".
  const filterResultCount = (draft: FilterValues) => {
    const draftPosition = singleValue(filterGroups[0], draft);
    return filterPlayers(idpPlayers.length > 0 && isIdpPositionFilter(draftPosition) ? idpPlayers : offensePool, {
      search,
      position: draftPosition,
      ageFilter: singleValue(filterGroups[1], draft) as PlayersAgeFilter,
      statusFilter: singleValue(filterGroups[2], draft) as PlayersStatusFilter,
      availabilityFilter: singleValue(filterGroups[3], draft) as PlayersAvailabilityFilter,
      rosterFilter: singleValue(filterGroups[4], draft) as PlayersRosterFilter,
      rosteredPlayerIds,
    }).length;
  };

  const pickSeasons = useMemo(() => groupPicksBySeason(visibleDraftPicks(picks, "league", "")), [picks]);

  return (
    <main className="page-shell">
      <header className="flex flex-col gap-1">
        <PageTitle page="Players" leagueName={leagueName} />
      </header>

      {picks.length > 0 ? (
        <PillRow
          options={[
            { label: "Players", value: "players", glyph: "players" },
            { label: "Picks", value: "picks", glyph: "picks" },
          ]}
          active={view}
          onSelect={(value) => setView(value as PlayersView)}
          fullWidth
        />
      ) : null}

      {view === "players" ? (
        <>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search players"
              className="filter-input col-span-2 px-3 py-2 text-sm sm:flex-1 sm:min-w-[10rem]"
            />
            {/* Position is the filter people use most, so it stays one tap: a pill row that
                applies at once. Filters keeps everything else (age, status, health, roster). */}
            <div className="col-span-2 sm:col-span-1 sm:order-first min-w-0">
              <PillRow
                variant="scroll"
                ariaLabel="Position"
                options={positionOptions.map((pos) => ({ label: pos === "ALL" ? "All" : pos, value: pos }))}
                active={position}
                onSelect={setPosition}
              />
            </div>
            <div className="col-span-2 sm:col-span-1">
              <FilterSheet
                groups={filterGroups}
                values={filterValues}
                resultCount={filterResultCount}
                onApply={(next) => {
                  setPosition(singleValue(filterGroups[0], next));
                  setAgeFilter(singleValue(filterGroups[1], next) as PlayersAgeFilter);
                  setStatusFilter(singleValue(filterGroups[2], next) as PlayersStatusFilter);
                  setAvailabilityFilter(singleValue(filterGroups[3], next) as PlayersAvailabilityFilter);
                  setRosterFilter(singleValue(filterGroups[4], next) as PlayersRosterFilter);
                }}
              />
            </div>
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
            <select aria-label="Sort by"
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
                  idpConfidence={idpSelected ? idpConfidenceById.get(player.player_id) ?? "low" : undefined}
                />
              ))}
            </div>
          )}
          {idpSelected ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {idpMethodNote(idp)}
            </p>
          ) : null}
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
                  <PickRow key={pick.pick_id} {...draftPickRowProps(pick, true)} showDivider={index < seasonPicks.length - 1} />
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
