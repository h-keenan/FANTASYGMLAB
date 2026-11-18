import { CompactModule } from "@/components/ui/CompactModule";
import { StatStrip, type StatStripItem } from "@/components/StatStrip";
import { formatRank, rankFill } from "@/components/SnapshotTile";
import { TERMS } from "@/lib/terms";
import type { TeamRanking } from "@/lib/api";

/** Whether the team carries any roster analysis beyond the plain rank tiles (mobile twin: TeamAnalysisPanel.hasRosterAnalysis). */
export function hasRosterAnalysis(team: TeamRanking): boolean {
  return Boolean(
    team.archetype_explanation ||
      team.archetype_strengths.length > 0 ||
      team.archetype_risks.length > 0 ||
      team.archetype_recommendations.length > 0 ||
      team.franchise_rank != null ||
      team.bench_rank != null,
  );
}

/** The six rank tiles of the app's Team Analytics (Roster Power, Long term, Draft Capital, Starters, Bench, Age), real server ranks only. */
export function buildTeamAnalyticsTiles(team: TeamRanking, leagueSize: number): StatStripItem[] {
  const tile = (
    glyph: StatStripItem["glyph"],
    insight: NonNullable<StatStripItem["insight"]>,
    label: string,
    rank: number | null,
    tied: boolean,
  ): StatStripItem | null =>
    rank == null ? null : { glyph, insight, label, value: formatRank(rank, tied), fill: rankFill(rank, leagueSize) };
  return [
    tile("power", "power", "Roster Power", team.power_rank, team.power_rank_tied),
    tile("franchise", "franchise", TERMS.longTerm, team.franchise_rank, team.franchise_rank_tied),
    tile("draft", "draft_capital", "Draft Capital", team.draft_capital_rank, team.draft_capital_rank_tied),
    tile("starter", "starter", "Starters", team.starter_rank, team.starter_rank_tied),
    tile("bench", "bench", "Bench", team.bench_rank, team.bench_rank_tied),
    tile("age", "age", "Age", team.age_rank, team.age_rank_tied),
  ].filter((item): item is StatStripItem => item !== null);
}

function DetailList({ label, items, color }: { label: string; items: string[]; color: string }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs font-bold uppercase" style={{ color, letterSpacing: "0.04em" }}>{label}</p>
      <ul className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {items.map((item, index) => (
          <li key={`${label}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * My Team's Team Analytics: the rank tiles (each a shortcut to its league board, Draft Capital to the Draft Center rankings) and the
 * archetype read (why, strengths, risks, recommendations, trade behavior). Collapsed it reads as a summary; opens on tap.
 * Mobile twin: the "team.analytics" CompactModule around TeamAnalysisPanel in mobile/src/screens/MyTeamScreen.tsx.
 */
export function TeamAnalyticsModule({
  team,
  leagueSize,
  leagueId,
  leagueName,
}: {
  team: TeamRanking;
  leagueSize: number;
  leagueId: string;
  leagueName: string;
}) {
  const tiles = buildTeamAnalyticsTiles(team, leagueSize);
  const hasTradeContext = Boolean(team.trade_tendency) && team.trade_tendency !== "Neutral";
  return (
    <CompactModule
      id="team.analytics"
      title="Team Analytics"
      testId="team-analytics"
      tone="muted"
      parts={[
        ...tiles.slice(0, 4).map((tile) => ({ key: tile.label, text: `${tile.label} ${tile.value}` })),
      ]}
    >
      <div className="flex flex-col gap-3">
        {tiles.length > 0 ? <StatStrip items={tiles} columns={3} league={leagueId ? { id: leagueId, name: leagueName } : undefined} /> : null}
        {team.archetype_explanation ? <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{team.archetype_explanation}</p> : null}
        <DetailList label="Strengths" items={team.archetype_strengths} color="var(--color-success)" />
        <DetailList label="Risks" items={team.archetype_risks} color="var(--color-warning)" />
        <DetailList label="Recommendations" items={team.archetype_recommendations} color="var(--color-accent)" />
        {hasTradeContext ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Trade behavior: {team.trade_tendency} ({team.trade_tendency_buy_count ?? 0} acquired · {team.trade_tendency_sell_count ?? 0} sent)
          </p>
        ) : null}
      </div>
    </CompactModule>
  );
}
