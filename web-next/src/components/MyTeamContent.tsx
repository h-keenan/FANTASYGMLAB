import { PlayerIdentity } from "@/components/PlayerRow";
import { ToneBadge } from "@/components/ToneBadge";
import { InfoTip } from "@/components/InfoTip";
import { StatStrip, type StatStripItem } from "@/components/StatStrip";
import { RosterCompositionBar, RosterTabs, TeamAnalysisList, type RosterTab } from "@/components/MyTeamSections";
import { buildRosterComposition, buildTeamAnalysisRows } from "@/lib/myTeamAnalysis";
import type { ReactNode } from "react";
import { PillRow } from "@/components/PillRow";
import type { KeepersResponse, LineupPlayer, MyTeamNeedsResponse, MyTeamResponse, TeamRanking } from "@/lib/api";
import { SectionHeading } from "@/components/SectionHeading";
import { formatRank } from "@/components/SnapshotTile";
import { ValueRing } from "@/components/ValueRing";
import {
  buildConstructionObservations,
  buildPositionGroupItems,
  formatScore,
  myTeamReasonMessage,
  openSlotsMessage,
  sumScore,
} from "@/lib/myTeamPresentation";
import { metricToneBand, percentileFromRank, positionTextClass } from "@/lib/playerPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";

/**
 * Ports modules/my_team_ui.py's render_my_team_workspace for Revision 2 —
 * see the PR description for the exact section-by-section scope line.
 * Covered: Team Snapshot (Team Value ring + archetype + Roster Signals
 * tiles), Strength & Pressure, Position Groups, and the full Starters/
 * Bench lineup with the circular OVR gauge and canonical position colors.
 * Deliberately NOT covered (same "lineup view only" boundary
 * GET .../my-team's own docstring already draws): the Strategy gateway
 * (team-strategy override, persisted roles), Roster Decisions
 * (Untouchables/trade-hold/drop — persisted per-user tags), the Roster
 * Actions tiles (Trade/Waiver/Immediate — fed by the untouchables-aware
 * trade engine), and the Prospect Watchlist. Those all need either new
 * stateful product surface or heavier recommendation-engine wiring, not a
 * thin wrapper — an explicit, separate follow-up rather than a silent
 * scope cut.
 */

// coridian_, 2026-10-18: "the bench should be in order so. QBs, RBs, WRs,
// TEs, K, DST" — any position not in this list (a rare/unknown value)
// sorts after every known one rather than being dropped or erroring.
const BENCH_POSITION_ORDER = ["QB", "RB", "WR", "TE", "K", "DST"];
function positionSortIndex(position: string | null | undefined): number {
  const index = BENCH_POSITION_ORDER.indexOf((position || "").toUpperCase());
  return index === -1 ? BENCH_POSITION_ORDER.length : index;
}

function positionRoomText(room: string): ReactNode {
  const cls = positionTextClass(room);
  return (
    <span key={room} className={cls} style={cls ? undefined : { color: "var(--color-text-primary)" }}>
      {room}
    </span>
  );
}

function joinRooms(rooms: string[]): ReactNode {
  return rooms.map((room, index) => (
    <span key={room}>
      {index > 0 ? " / " : null}
      {positionRoomText(room)}
    </span>
  ));
}

const KEEPER_BASIS_LABEL: Record<string, string> = {
  league_setting: "from the league setting",
  previous_draft: "from last year's draft keepers",
  declared_keepers: "from your declared keepers",
};

export function MyTeamContent({
  leagueName,
  myTeam,
  needs,
  teamRanking,
  leagueSize,
  highlightPlayerId,
  keepers = null,
  onKeeperRoundPenalty,
}: {
  leagueName: string;
  myTeam: MyTeamResponse;
  needs: MyTeamNeedsResponse | null;
  teamRanking: TeamRanking | null;
  leagueSize: number;
  /** See components/HighlightTarget.tsx — a GM Plan/Dashboard injury-alert or
   * value-trend tile's specific roster player, threaded through as
   * ?playerId= (gamePlanTileHref). */
  highlightPlayerId?: string;
  /** GET .../keepers (keeper leagues only); null/absent renders nothing. */
  keepers?: KeepersResponse | null;
  /** Persist the per-league keeper round penalty; omit to hide the control. */
  onKeeperRoundPenalty?: (penalty: number) => void;
}) {
  const notice = myTeam.reason ? myTeamReasonMessage(myTeam.reason) : null;
  if (notice) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {notice}
        </p>
      </main>
    );
  }

  const starters = myTeam.starters;
  const bench = myTeam.bench;
  // coridian_, 2026-10-18, screenshot: "the bench should be in order so.
  // QBs, RBs, WRs, TEs, K, DST" — the API returns bench players in value
  // order (mixing positions together); sort is stable, so within each
  // position group the existing value order is preserved.
  const byPosition = (list: LineupPlayer[]) =>
    [...list].sort((a, b) => positionSortIndex(a.position) - positionSortIndex(b.position));
  // Best ball (Sleeper settings.best_ball): Sleeper sets the lineup itself
  // from the highest weekly scorers, so there's no suggested starters/bench
  // split to recommend — one position-ordered roster list instead, with the
  // optimizer's suggested slot labels stripped.
  const bestBall = myTeam.best_ball === true;
  const activeBench = byPosition(
    [...(bestBall ? starters : []), ...bench.filter((p) => p.roster_slot !== "ir" && p.roster_slot !== "taxi")].map(
      (p) => (bestBall ? { ...p, slot: null } : p),
    ),
  );
  const irBench = byPosition(bench.filter((p) => p.roster_slot === "ir"));
  const taxiBench = byPosition(bench.filter((p) => p.roster_slot === "taxi"));

  const startersTotalValue = sumScore(starters);
  const teamTotalValue = sumScore(starters) + sumScore(bench);

  const showFranchiseConstruction = needs?.show_franchise_construction ?? false;
  const valuePercentile = teamRanking ? percentileFromRank(teamRanking.power_rank, leagueSize) : null;

  const observations = needs
    ? buildConstructionObservations({
        strengths: needs.strengths,
        weaknesses: needs.weaknesses,
        // GET .../my-team-needs is scoped to the Strength & Pressure/
        // Position Groups fields alone, not health_flag (that's
        // GET .../dashboard's team_snapshot) — the "injury context" health
        // fallback below the weaknesses check simply never fires here
        // rather than pulling in a second fetch for one rarely-hit branch.
        healthFlag: null,
        draftCapitalRank: teamRanking?.draft_capital_rank ?? null,
        draftCapitalRankTied: teamRanking?.draft_capital_rank_tied ?? false,
        showFranchiseConstruction,
        archetypeStrengths: teamRanking?.archetype_strengths,
        archetypeLabel: teamRanking?.archetype_label,
        formatRank,
      })
    : [];

  const positionGroupItems = needs
    ? buildPositionGroupItems({
        positionGroups: needs.position_groups,
        strengths: needs.strengths,
        superflex: needs.superflex,
        tePremium: needs.te_premium,
      })
    : [];

  const analysisRows = buildTeamAnalysisRows(positionGroupItems);

  const tabs: RosterTab[] = bestBall
    ? [{ value: "starters", label: "Roster", players: activeBench }]
    : [
        { value: "starters", label: "Starters", players: starters, showSlot: true },
        { value: "bench", label: "Bench", players: activeBench, muted: true },
      ];
  if (irBench.length > 0) tabs.push({ value: "ir", label: "IR", players: irBench, muted: true });
  if (taxiBench.length > 0) tabs.push({ value: "taxi", label: "Taxi", players: taxiBench, muted: true });
  // IDP leagues only: rostered defenders (model value), else the tab is absent.
  const idpPlayers = myTeam.idp_players ?? [];
  if (idpPlayers.length > 0) tabs.push({ value: "idp", label: "IDP", players: idpPlayers, muted: true });

  const composition = buildRosterComposition(
    bestBall
      ? [
          { key: "roster", label: "Roster", players: activeBench },
          { key: "ir", label: "IR", players: irBench },
          { key: "taxi", label: "Taxi", players: taxiBench },
        ]
      : [
          { key: "starters", label: "Starters", players: starters },
          { key: "bench", label: "Bench", players: activeBench },
          { key: "ir", label: "IR", players: irBench },
          { key: "taxi", label: "Taxi", players: taxiBench },
        ],
  );

  const record = teamRanking
    ? `${teamRanking.wins ?? 0}-${teamRanking.losses ?? 0}${teamRanking.ties ? `-${teamRanking.ties}` : ""}`
    : "—";
  const snapshotItems: StatStripItem[] = [
    { glyph: "record", label: "Record", value: record },
    { glyph: "power", label: "Power Rank", value: formatRank(teamRanking?.power_rank ?? null, teamRanking?.power_rank_tied ?? false) },
    ...(showFranchiseConstruction
      ? [
          {
            glyph: "franchise" as const,
            label: "Franchise Rank",
            value: formatRank(teamRanking?.franchise_rank ?? null, teamRanking?.franchise_rank_tied ?? false),
          },
        ]
      : []),
    { glyph: "starter", label: "Starter Strength", value: formatRank(teamRanking?.starter_rank ?? null, teamRanking?.starter_rank_tied ?? false) },
    { glyph: "bench", label: "Bench Strength", value: formatRank(teamRanking?.bench_rank ?? null, teamRanking?.bench_rank_tied ?? false) },
    { glyph: "age", label: "Avg Age", value: teamRanking?.average_age != null ? teamRanking.average_age.toFixed(1) : "—" },
  ];

  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          My Team
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
      </header>

      <section className="flex flex-col gap-3" aria-labelledby="team-snapshot-heading">
        <SectionHeading>
          <span id="team-snapshot-heading">Team Snapshot</span>
        </SectionHeading>
        <div className="flex items-center gap-4">
          <ValueRing
            percent={valuePercentile}
            tone={metricToneBand(valuePercentile) || "mid"}
            display={valuePercentile !== null ? String(Math.round(valuePercentile)) : "—"}
            ariaLabel={
              valuePercentile !== null ? `Team value ${Math.round(valuePercentile)}th percentile` : "Team value unavailable"
            }
          />
          <div className="flex flex-col gap-1 items-start min-w-0">
            {teamRanking?.archetype_label ? (
              <span
                className="px-2 py-1 text-xs font-extrabold uppercase"
                style={{ background: "var(--color-accent)", color: "var(--color-bg)" }}
              >
                {teamRanking.archetype_label}
              </span>
            ) : null}
            <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
              Team Value
            </span>
            <span style={{ font: "var(--type-primary-metric)" }}>{formatScore(teamTotalValue)}</span>
          </div>
        </div>
        <StatStrip items={snapshotItems.slice(0, 3)} columns={3} />
        <StatStrip items={snapshotItems.slice(3)} columns={3} />
      </section>

      {analysisRows.length > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="team-analysis-heading">
          <SectionHeading>
            <span id="team-analysis-heading">Team Analysis</span>
          </SectionHeading>
          <TeamAnalysisList rows={analysisRows} />
          {observations.length > 0 || needs?.biggest_need ? (
            <InfoTip label="Roster notes">
              <div className="flex flex-col gap-2">
                {needs?.biggest_need ? (
                  <p>
                    <strong>{needs.biggest_need.label}: </strong>
                    {(() => {
                      const cls = positionTextClass(needs.biggest_need.value);
                      return cls ? <span className={cls}>{needs.biggest_need.value}</span> : needs.biggest_need.value;
                    })()}
                    {". "}
                    {needs.biggest_need.note}
                  </p>
                ) : null}
                {observations.map((observation) => (
                  <p key={observation.label + observation.titlePrefix + observation.titleSuffix}>
                    <strong>
                      {observation.titlePrefix}
                      {observation.rooms.length > 0 ? joinRooms(observation.rooms) : null}
                      {observation.titleSuffix}
                      {": "}
                    </strong>
                    {observation.body}
                  </p>
                ))}
              </div>
            </InfoTip>
          ) : null}
        </section>
      ) : null}

      <section className="flex flex-col gap-3" aria-labelledby="roster-heading">
        <div className="flex items-baseline justify-between">
          <SectionHeading>
            <span id="roster-heading">Your Roster</span>
          </SectionHeading>
          {!bestBall && starters.length > 0 ? (
            <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
              Starters Value {formatScore(startersTotalValue)}
            </span>
          ) : null}
        </div>
        {bestBall && myTeam.lineup_advice_message ? (
          <p className="glass-surface text-sm p-4" style={{ color: "var(--color-text-secondary)" }}>
            {myTeam.lineup_advice_message}
          </p>
        ) : null}
        <RosterTabs
          tabs={tabs}
          keepers={keepers?.players}
          highlightPlayerId={highlightPlayerId}
          emptyText={bestBall ? "No players on this roster." : "Nobody here yet."}
          topNote={
            <>
              {myTeam.lineup_basis_label && myTeam.lineup_basis && myTeam.lineup_basis !== "season_value" && !bestBall ? (
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {myTeam.week ? `Week ${myTeam.week}. ` : ""}
                  {myTeam.lineup_basis_label}
                </p>
              ) : null}
              {openSlotsMessage(myTeam.open_slots) ? (
                <p className="text-sm font-bold" role="status" style={{ color: "var(--color-warning)" }}>
                  {openSlotsMessage(myTeam.open_slots)}
                </p>
              ) : null}
            </>
          }
        />
      </section>

      {composition.length > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="composition-heading">
          <SectionHeading>
            <span id="composition-heading">Roster Composition</span>
          </SectionHeading>
          <RosterCompositionBar segments={composition} />
        </section>
      ) : null}

      {keepers?.is_keeper_league && (keepers.candidates?.length ?? 0) > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="keeper-candidates-heading">
          <SectionHeading>
            <span id="keeper-candidates-heading">Keeper candidates</span>
          </SectionHeading>
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Keep up to {keepers.keep_count} {KEEPER_BASIS_LABEL[keepers.keep_count_basis ?? ""] ?? ""}. Rounds and
            surplus are estimates.
          </p>
          {onKeeperRoundPenalty ? (
            <div className="flex items-center gap-3">
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                Round penalty
              </span>
              <PillRow
                options={[0, 1, 2, 3].map((n) => ({ label: String(n), value: String(n) }))}
                active={String(keepers.round_penalty ?? 0)}
                onSelect={(value) => onKeeperRoundPenalty(Number(value))}
              />
            </div>
          ) : null}
          <div>
            {keepers.candidates!.map((c) => (
              <div
                key={c.player_id}
                className="flex items-center gap-3 py-2"
                style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
              >
                <PlayerIdentity
                  identity={{ player_id: c.player_id, name: c.name, position: c.position, sourceLabel: "My Team" }}
                  playerId={c.player_id}
                  name={c.name}
                  position={c.position}
                  className="flex-1 min-w-0"
                >
                  {c.reason}
                </PlayerIdentity>
                {keepers.recommended_ids?.includes(c.player_id) ? (
                  <ToneBadge label="Keep" color="var(--color-success)" />
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}
      <ValuesCredit />
    </main>
  );
}
