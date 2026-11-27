import { TERMS } from "@/lib/terms";
import { PageTabBar } from "@/components/PageTabBar";
import { BEGINNER_HELP } from "@/lib/experienceCopy";
import { PlayerIdentity } from "@/components/PlayerRow";
import { ToneBadge } from "@/components/ToneBadge";
import { InfoMark } from "@/components/ui/InfoMark";
import { StatStrip, type StatStripItem } from "@/components/StatStrip";
import { RosterCompositionBar, RosterSections, TeamAnalysisList, type RosterTab } from "@/components/MyTeamSections";
import { CompactModule } from "@/components/ui/CompactModule";
import { TodayRooms } from "@/components/TodayGlance";
import { LeagueTypeControl, useGuillotineState } from "@/components/GuillotineCard";
import { buildTeamStatusPositions } from "@/lib/teamStatus";
import { todayRoomChips } from "@/lib/todayView";
import { StatStripModule } from "@/components/ui/ModuleTemplates";
import { StatusHeader } from "@/components/ui/StatusHeader";
import { buildTeamStatusHeader, ordinalRank, rosterAttentionItems } from "@/lib/statusHeader";
import { isActionableLineupIssue, leftGame } from "@/lib/lineupLock";
import { playerSurname } from "@/lib/playerNameDisplay";
import { listSummaryParts } from "@/lib/moduleTemplates";
import { buildRosterComposition, buildTeamAnalysisRows } from "@/lib/myTeamAnalysis";
import type { ReactNode } from "react";
import { PillRow } from "@/components/PillRow";
import type { KeepersResponse, LineupPlayer, MyTeamNeedsResponse, MyTeamResponse, TeamRanking } from "@/lib/api";
import { usePageHelp } from "@/components/PageHelpLines";
import { formatRank, rankFill } from "@/components/SnapshotTile";
import {
  buildConstructionObservations,
  buildPositionGroupItems,
  formatScore,
  myTeamReasonMessage,
  openSlotsMessage,
  sumScore,
} from "@/lib/myTeamPresentation";
import { percentileFromRank, positionTextClass } from "@/lib/playerPresentation";
import { buildRosterBasis } from "@/lib/rosterBasis";
import { ValuesCredit } from "@/components/ValuesCredit";
import { NextSteps } from "@/components/NextSteps";
import { TeamArchetypeRead, hasArchetypeRead } from "@/components/TeamArchetypeRead";
import { PageTitle } from "@/components/PageTitle";
import { FreshnessLabel } from "@/components/ui/FreshnessLabel";

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

/** Win share as a 0..1 bar fill; null before any game is played. */
function winShare(wins: number | null, losses: number | null, ties: number | null): number | null {
  const w = wins ?? 0;
  const games = w + (losses ?? 0) + (ties ?? 0);
  return games > 0 ? (w + (ties ?? 0) / 2) / games : null;
}

/** Fewest teams for which a league percentile is shown (mobile twin: MyTeamScreen). */
const MIN_TEAMS_FOR_PERCENTILE = 4;

const KEEPER_BASIS_LABEL: Record<string, string> = {
  league_setting: "from the league setting",
  previous_draft: "from last year's draft keepers",
  declared_keepers: "from your declared keepers",
};

export function MyTeamContent({
  leagueId = "",
  leagueName,
  myTeam,
  needs,
  teamRanking,
  leagueSize,
  highlightPlayerId,
  keepers = null,
  onKeeperRoundPenalty,
}: {
  /** Enables the "Act on a need" links; omitted: no links. */
  leagueId?: string;
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
  const guillotine = useGuillotineState(leagueId || undefined);
  const pageHelp = usePageHelp([BEGINNER_HELP.myTeamIntro, BEGINNER_HELP.myTeamValueTiers]);
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
    // One roster basis for web and app (lib/rosterBasis.ts): position-ordered bench, and the best-ball single roster list.
  const bestBall = myTeam.best_ball === true;
  const { activeBench, irBench, taxiBench } = buildRosterBasis(starters, bench, bestBall);

  const startersTotalValue = sumScore(starters);
  const teamTotalValue = sumScore(starters) + sumScore(bench);

  const roomChips = todayRoomChips(buildTeamStatusPositions(needs));
  const showFranchiseConstruction = needs?.show_franchise_construction ?? false;
  // A percentile against a tiny league ("0th percentile of 2 teams") says nothing: show it only with enough teams.
  const valuePercentile = teamRanking && leagueSize >= MIN_TEAMS_FOR_PERCENTILE ? percentileFromRank(teamRanking.power_rank, leagueSize) : null;

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
    { glyph: "record", insight: "record", label: "Record", value: record, fill: teamRanking ? winShare(teamRanking.wins, teamRanking.losses, teamRanking.ties) : null },
    { glyph: "power", insight: "power", why: "power_rank", label: TERMS.thisSeason, value: formatRank(teamRanking?.power_rank ?? null, teamRanking?.power_rank_tied ?? false), fill: rankFill(teamRanking?.power_rank, leagueSize) },
    ...(showFranchiseConstruction
      ? [
          {
            glyph: "franchise" as const,
            insight: "franchise" as const,
            why: "franchise_rank" as const,
            label: TERMS.longTerm,
            value: formatRank(teamRanking?.franchise_rank ?? null, teamRanking?.franchise_rank_tied ?? false),
            fill: rankFill(teamRanking?.franchise_rank, leagueSize),
          },
        ]
      : []),
    ...(showFranchiseConstruction && teamRanking?.draft_capital_rank != null
      ? [{ glyph: "draft" as const, insight: "draft_capital" as const, label: "Draft Capital", value: formatRank(teamRanking.draft_capital_rank, teamRanking.draft_capital_rank_tied ?? false), fill: rankFill(teamRanking.draft_capital_rank, leagueSize) }]
      : []),
    { glyph: "starter", insight: "starter", why: "starter_strength", label: "Starter Strength", value: formatRank(teamRanking?.starter_rank ?? null, teamRanking?.starter_rank_tied ?? false), fill: rankFill(teamRanking?.starter_rank, leagueSize) },
    { glyph: "bench", insight: "bench", why: "bench_strength", label: "Bench Strength", value: formatRank(teamRanking?.bench_rank ?? null, teamRanking?.bench_rank_tied ?? false), fill: rankFill(teamRanking?.bench_rank, leagueSize) },
  ];

  const openSlots = openSlotsMessage(myTeam.open_slots);
  // The status header: ring = how high the roster's value sits in the league, holes and injuries as mini stats, the
  // starters who cannot play as player rows. A best-ball roster has no lineup to fix, so no holes or rows.
  const lineupHref = `/matchup/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`;
  const flaggedStarters = bestBall ? 0 : starters.filter((p) => isActionableLineupIssue(p)).length;
  const teamStatusModel = buildTeamStatusHeader({
    teamValue: formatScore(teamTotalValue),
    valuePercentile,
    valueRank: teamRanking?.power_rank ?? null,
    leagueSize: leagueSize > 0 ? leagueSize : null,
    context:
      valuePercentile !== null
        ? `${ordinalRank(teamRanking?.power_rank ?? 0)} of ${leagueSize} teams${!bestBall && starters.length > 0 ? ` · Starters ${formatScore(startersTotalValue)}` : ""}`
        : !bestBall && starters.length > 0
          ? `Starters ${formatScore(startersTotalValue)}`
          : null,
    openSlots: bestBall ? 0 : (myTeam.open_slots ?? []).length,
    flaggedStarters,
    injuredStarters: bestBall ? 0 : starters.filter((p) => p.injury_label && p.injury_label.trim()).length,
    leftGameNames: bestBall ? [] : starters.filter((p) => leftGame(p) && p.name).map((p) => playerSurname(p.name as string)),
    attention: bestBall || !leagueId ? [] : rosterAttentionItems(starters, 3, lineupHref),
    hrefs: { lineup: lineupHref },
  });
  const analysisParts = [
    needs?.biggest_need ? { key: "need", text: `Biggest need: ${needs.biggest_need.value}`, tone: "warning" as const, strong: true } : null,
    ...analysisRows.slice(0, 4).map((row) => ({
      key: row.position,
      text: `${row.position} ${row.status}`,
      tone: row.tone === "success" ? ("success" as const) : row.tone === "danger" ? ("danger" as const) : row.tone === "warning" ? ("warning" as const) : undefined,
    })),
  ];
  const keeperList = keepers?.is_keeper_league ? (keepers.candidates ?? []) : [];

  return (
    <main className="page-shell">
      {/* The page's one tab row. Everything below is a Hero plus modules that read while collapsed. */}
      {leagueId ? <PageTabBar family="team" active="roster" leagueId={leagueId} leagueName={leagueName} /> : null}
      <header className="flex flex-col gap-1">
        <PageTitle page="My Team" leagueName={leagueName} info={pageHelp} />
        {myTeam.sleeper_data_as_of ? <FreshnessLabel datasets={[]} report={null} leagueAsOf={myTeam.sleeper_data_as_of} className="block text-xs" /> : null}
      </header>

      <StatusHeader
        model={teamStatusModel}
        badge={teamRanking?.archetype_label ? <ToneBadge label={teamRanking.archetype_label} color="var(--color-accent)" /> : undefined}
        testId="team-hero"
      />

      <StatStripModule
        id="team.snapshot"
        title="Team Snapshot"
        items={snapshotItems}
        league={{ id: leagueId, name: leagueName }}
        footer={teamRanking && hasArchetypeRead(teamRanking) ? <TeamArchetypeRead team={teamRanking} league={leagueId ? { id: leagueId, name: leagueName } : undefined} /> : undefined}
        infoGlossary={
          showFranchiseConstruction
            ? ["powerRank", "franchiseRank", "starterStrength", "benchStrength", "averageAge", "draftPicks", "pqv", "superflex", "tep"]
            : ["powerRank", "starterStrength", "benchStrength", "averageAge"]
        }
      />

      {/* Position rooms (moved here from Today): one chip per room, opening into a meter bar each. */}
      {roomChips.length > 0 && leagueId ? <TodayRooms chips={roomChips} tradeHref={`/trade-hub/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`} /> : null}

      {analysisRows.length > 0 ? (
        <CompactModule id="team.analysis" title="Team Analysis" testId="team-analysis" parts={analysisParts}>
          <TeamAnalysisList rows={analysisRows} />
          {observations.length > 0 || needs?.biggest_need ? (
            <div className="flex items-center">
              <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
                Roster notes
              </span>
              <InfoMark label="roster notes">
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
              </InfoMark>
            </div>
          ) : null}
          {needs && needs.weaknesses.length > 0 ? (
            <NextSteps title="Act on a need" steps={["waivers", "trade-hub"]} leagueId={leagueId} leagueName={leagueName} />
          ) : null}
        </CompactModule>
      ) : null}

      {bestBall && myTeam.lineup_advice_message ? (
        <p className="glass-surface text-sm p-4" style={{ color: "var(--color-text-secondary)" }}>
          {myTeam.lineup_advice_message}
        </p>
      ) : null}
      <RosterSections
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
            {openSlots ? (
              <p className="text-sm font-bold" role="status" style={{ color: "var(--color-warning)" }}>
                {openSlots}
              </p>
            ) : null}
          </>
        }
      />

      {composition.length > 0 ? (
        <CompactModule
          id="team.composition"
          title="Roster Composition"
          tone="muted"
          parts={composition.map((segment) => ({ key: segment.key, text: `${segment.label} ${segment.percent}%` }))}
        >
          <RosterCompositionBar segments={composition} />
        </CompactModule>
      ) : null}

      {keeperList.length > 0 && keepers ? (
        <CompactModule
          id="team.keepers"
          title="Keeper candidates"
          tone="success"
          parts={listSummaryParts({
            count: keeperList.length,
            noun: "candidate",
            highlights: [
              keepers.keep_count != null ? `Keep up to ${keepers.keep_count}` : null,
              (keepers.recommended_ids?.length ?? 0) > 0 ? `${keepers.recommended_ids?.length} recommended` : null,
            ],
          })}
        >
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Keep up to {keepers.keep_count} {KEEPER_BASIS_LABEL[keepers.keep_count_basis ?? ""] ?? ""}. Rounds and surplus are estimates.
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
            {keeperList.map((c) => (
              <div key={c.player_id} className="flex items-center gap-3 py-2" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
                <PlayerIdentity
                  identity={{ player_id: c.player_id, name: c.name, position: c.position, sourceLabel: "My Team" }}
                  playerId={c.player_id}
                  name={c.name}
                  position={c.position}
                  className="flex-1 min-w-0"
                >
                  {c.reason}
                </PlayerIdentity>
                {keepers.recommended_ids?.includes(c.player_id) ? <ToneBadge label="Keep" color="var(--color-success)" /> : null}
              </div>
            ))}
          </div>
        </CompactModule>
      ) : null}
      {/* League settings (moved here from Today's More): the league-type override. Renders nothing until the status has loaded. */}
      {leagueId && guillotine.data?.ok && guillotine.data.league_type_override !== undefined ? (
        <CompactModule id="team.league-settings" title="League settings" testId="league-settings" tone="muted" parts={[{ key: "type", text: "League type" }]}>
          <LeagueTypeControl leagueId={leagueId} data={guillotine.data} onChanged={guillotine.reload} />
        </CompactModule>
      ) : null}

      <ValuesCredit freshness={["values", "injuries"]} />
    </main>
  );
}
