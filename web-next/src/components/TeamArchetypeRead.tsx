import type { TeamRanking } from "@/lib/api";

/** Whether the team carries an archetype read worth a section (mobile twin: hasArchetypeRead in components/TeamAnalysisPanel.tsx). */
export function hasArchetypeRead(team: TeamRanking): boolean {
  return Boolean(
    team.archetype_explanation ||
      team.archetype_strengths.length > 0 ||
      team.archetype_risks.length > 0 ||
      team.archetype_recommendations.length > 0 ||
      (team.trade_tendency && team.trade_tendency !== "Neutral"),
  );
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
 * The archetype read under My Team's Team Snapshot tiles (shown when the module is opened): why, strengths, risks,
 * recommendations and trade behavior. Mobile twin: TeamArchetypeRead in mobile/src/components/TeamAnalysisPanel.tsx.
 */
export function TeamArchetypeRead({ team }: { team: TeamRanking }) {
  const hasTradeContext = Boolean(team.trade_tendency) && team.trade_tendency !== "Neutral";
  return (
    <div className="flex flex-col gap-3" data-testid="team-archetype-read">
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
  );
}
