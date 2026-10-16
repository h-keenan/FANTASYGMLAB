import type { ReactNode } from "react";
import type { LineupPlayer, MyTeamNeedsResponse, MyTeamResponse, TeamRanking } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { SnapshotTile, formatRank } from "@/components/SnapshotTile";
import { ValueRing } from "@/components/ValueRing";
import {
  buildConstructionObservations,
  buildPositionGroupItems,
  formatScore,
  injuryTone,
  myTeamReasonMessage,
  sumScore,
} from "@/lib/myTeamPresentation";
import { metricToneBand, percentileFromRank, positionTextClass } from "@/lib/playerPresentation";

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

function LineupRow({ player, muted = false }: { player: LineupPlayer; muted?: boolean }) {
  const tone = injuryTone(player.injury_label);
  return (
    <div
      className="flex items-center gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentityTrigger
        identity={{ ...player, sourceLabel: "My Team" }}
        className="flex-1 flex items-center gap-3 min-w-0"
      >
        <OvrGauge rating={player.overall_rating} size="sm" />
        <PositionBadge position={player.position} />
        <div className="flex-1 flex flex-col gap-0.5 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold truncate" style={{ color: muted ? "var(--color-text-secondary)" : "var(--color-text-primary)" }}>
              {player.name || "Unknown player"}
            </span>
            {player.injury_label ? (
              <span
                className="px-1 text-xs font-bold uppercase"
                style={{
                  color: tone === "danger" ? "var(--color-danger)" : tone === "warning" ? "var(--color-warning)" : "var(--color-text-muted)",
                }}
              >
                {player.injury_label}
              </span>
            ) : null}
          </div>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {player.team || "FA"} {player.slot && player.slot !== "BENCH" ? `· ${player.slot}` : ""}
          </span>
        </div>
      </PlayerIdentityTrigger>
      <div className="flex flex-col items-end gap-0.5 shrink-0">
        <span className="text-sm font-extrabold" style={{ color: muted ? "var(--color-text-secondary)" : "var(--color-accent)" }}>
          {player.score !== null ? Math.round(player.score) : "—"}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          VALUE
        </span>
      </div>
    </div>
  );
}

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="uppercase" style={{ font: "var(--type-section-title)", letterSpacing: "0.02em" }}>
      {children}
    </h2>
  );
}

export function MyTeamContent({
  leagueName,
  myTeam,
  needs,
  teamRanking,
  leagueSize,
}: {
  leagueName: string;
  myTeam: MyTeamResponse;
  needs: MyTeamNeedsResponse | null;
  teamRanking: TeamRanking | null;
  leagueSize: number;
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
  const activeBench = bench.filter((p) => p.roster_slot !== "ir" && p.roster_slot !== "taxi");
  const irBench = bench.filter((p) => p.roster_slot === "ir");
  const taxiBench = bench.filter((p) => p.roster_slot === "taxi");

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
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex flex-col items-center gap-1">
            <ValueRing
              percent={valuePercentile}
              tone={metricToneBand(valuePercentile) || "mid"}
              display={valuePercentile !== null ? String(Math.round(valuePercentile)) : "—"}
              ariaLabel={
                valuePercentile !== null
                  ? `Team value ${Math.round(valuePercentile)}th percentile`
                  : "Team value unavailable"
              }
            />
            <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
              Team Value
            </span>
          </div>
          {teamRanking?.archetype_label ? (
            <span
              className="px-2 py-1 text-xs font-extrabold uppercase self-start"
              style={{ background: "var(--color-accent)", color: "var(--color-bg)" }}
            >
              {teamRanking.archetype_label}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-3">
          <SnapshotTile
            label="Record"
            value={
              teamRanking
                ? `${teamRanking.wins ?? 0}-${teamRanking.losses ?? 0}${teamRanking.ties ? `-${teamRanking.ties}` : ""}`
                : "—"
            }
          />
          <SnapshotTile label="Power Rank" value={formatRank(teamRanking?.power_rank ?? null, teamRanking?.power_rank_tied ?? false)} />
          {showFranchiseConstruction ? (
            <SnapshotTile
              label="Franchise Rank"
              value={formatRank(teamRanking?.franchise_rank ?? null, teamRanking?.franchise_rank_tied ?? false)}
            />
          ) : null}
          <SnapshotTile
            label="Starter Strength"
            value={formatRank(teamRanking?.starter_rank ?? null, teamRanking?.starter_rank_tied ?? false)}
          />
          <SnapshotTile label="Bench Strength" value={formatRank(teamRanking?.bench_rank ?? null, teamRanking?.bench_rank_tied ?? false)} />
          <SnapshotTile
            label="Avg Age"
            value={teamRanking?.average_age != null ? teamRanking.average_age.toFixed(1) : "—"}
          />
          <SnapshotTile label="Team Value" value={formatScore(teamTotalValue)} />
        </div>
      </section>

      {observations.length > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="strength-pressure-heading">
          <SectionHeading>
            <span id="strength-pressure-heading">Strength &amp; Pressure</span>
          </SectionHeading>
          <div className="grid gap-3 sm:grid-cols-2">
            {observations.map((observation) => (
              <div
                key={observation.label + observation.titlePrefix + observation.titleSuffix}
                className={`tone-${observation.tone} p-4 flex flex-col gap-1`}
                style={{ background: "var(--color-surface-secondary)" }}
              >
                <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                  {observation.label}
                </span>
                <span className="tone-value text-sm font-extrabold">
                  {observation.titlePrefix}
                  {observation.rooms.length > 0 ? joinRooms(observation.rooms) : null}
                  {observation.titleSuffix}
                </span>
                <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  {observation.body}
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {needs?.biggest_need ? (
        <section className="flex flex-col gap-3" aria-labelledby="biggest-need-heading">
          <SectionHeading>
            <span id="biggest-need-heading">{needs.biggest_need.label}</span>
          </SectionHeading>
          <div className="tone-need p-4 flex flex-col gap-1" style={{ background: "var(--color-surface-secondary)" }}>
            <span className="tone-value text-sm font-extrabold">
              {(() => {
                const cls = positionTextClass(needs.biggest_need.value);
                return cls ? <span className={cls}>{needs.biggest_need.value}</span> : needs.biggest_need.value;
              })()}
            </span>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {needs.biggest_need.note}
            </p>
          </div>
        </section>
      ) : null}

      {positionGroupItems.length > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="position-groups-heading">
          <SectionHeading>
            <span id="position-groups-heading">Position Groups</span>
          </SectionHeading>
          <div className="grid gap-3 sm:grid-cols-2">
            {positionGroupItems.map((item) => (
              <div
                key={item.position}
                className={`tone-${item.tone} p-4 flex flex-col gap-1`}
                style={{ background: "var(--color-surface-secondary)" }}
              >
                <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                  {item.label}
                </span>
                <span className="tone-value text-sm font-extrabold">
                  <span className={positionTextClass(item.position)}>{item.position}</span>
                  {item.contextSuffix}
                </span>
                <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  {item.body}
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="flex flex-col gap-3" aria-labelledby="starters-heading">
        <div className="flex items-baseline justify-between">
          <SectionHeading>
            <span id="starters-heading">Starters</span>
          </SectionHeading>
          <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
            Total Starters Value {formatScore(startersTotalValue)}
          </span>
        </div>
        {starters.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No suggested starters yet.
          </p>
        ) : (
          <div className="flex flex-col" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}>
            {starters.map((player) => (
              <LineupRow key={player.player_id} player={player} />
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="bench-heading">
        <SectionHeading>
          <span id="bench-heading">Bench</span>
        </SectionHeading>
        {bench.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No bench players.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {activeBench.length > 0 ? (
              <div className="flex flex-col" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}>
                {activeBench.map((player) => (
                  <LineupRow key={player.player_id} player={player} muted />
                ))}
              </div>
            ) : null}
            {irBench.length > 0 ? (
              <div className="flex flex-col gap-2">
                <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                  Injured Reserve
                </span>
                <div className="flex flex-col" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}>
                  {irBench.map((player) => (
                    <LineupRow key={player.player_id} player={player} muted />
                  ))}
                </div>
              </div>
            ) : null}
            {taxiBench.length > 0 ? (
              <div className="flex flex-col gap-2">
                <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                  Taxi Squad
                </span>
                <div className="flex flex-col" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}>
                  {taxiBench.map((player) => (
                    <LineupRow key={player.player_id} player={player} muted />
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}
