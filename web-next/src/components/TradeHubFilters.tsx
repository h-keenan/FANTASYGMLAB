import { trackUse } from "@/lib/analytics";
import type { TradeIdea } from "@/lib/api";
import { type TradeIdeaFilter, boardPositions, impactTagCounts } from "@/lib/tradeHubFilters";
import { SkeletonBlock } from "@/components/Skeleton";

function chipStyle(active: boolean) {
  return {
    color: active ? "var(--color-accent)" : "var(--color-text-secondary)",
    border: `1px solid ${active ? "var(--color-accent)" : "var(--color-border)"}`,
    background: active ? "color-mix(in srgb, var(--color-accent) 12%, transparent)" : "var(--color-surface-muted)",
    borderRadius: "var(--radius-pill)",
    minHeight: "2.5rem",
  } as const;
}

/**
 * Trade Hub filter chips: All (N), one chip per engine impact tag present on
 * the board (Buy Low / Sell High / High Impact), and a Positions picker. There
 * is no My Trades chip (every idea is built around the user's own players) and
 * no Leagues picker (Trade Hub is one league per view).
 */
export function TradeHubFilters({
  ideas,
  filter,
  onChange: rawOnChange,
}: {
  ideas: TradeIdea[];
  filter: TradeIdeaFilter;
  onChange: (next: TradeIdeaFilter) => void;
}) {
  const onChange = (next: TradeIdeaFilter) => {
    const kind = next.impact !== filter.impact ? "impact" : "position";
    trackUse("trade_hub_filters", "filter_changed", {
      props: { item_kind: kind, result: (kind === "impact" ? next.impact : next.position) || "all" },
    });
    rawOnChange(next);
  };
  const impacts = impactTagCounts(ideas);
  const positions = boardPositions(ideas);
  const allActive = !filter.impact && !filter.position;
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter trade ideas">
      <button
        type="button"
        onClick={() => onChange({ impact: null, position: null })}
        aria-pressed={allActive}
        className="px-4 text-sm font-bold"
        style={chipStyle(allActive)}
      >
        All ({ideas.length})
      </button>
      {impacts.map((entry) => {
        const active = filter.impact === entry.tag;
        return (
          <button
            key={entry.tag}
            type="button"
            onClick={() => onChange({ ...filter, impact: active ? null : entry.tag })}
            aria-pressed={active}
            className="px-4 text-sm font-bold"
            style={chipStyle(active)}
          >
            {entry.label} ({entry.count})
          </button>
        );
      })}
      {positions.length > 1 ? (
        <select
          aria-label="Positions"
          value={filter.position ?? ""}
          onChange={(event) => onChange({ ...filter, position: event.target.value || null })}
          className="px-3 text-sm font-bold"
          style={chipStyle(Boolean(filter.position))}
        >
          <option value="">Positions</option>
          {positions.map((pos) => (
            <option key={pos} value={pos}>
              {pos}
            </option>
          ))}
        </select>
      ) : null}
    </div>
  );
}

/** Loading placeholder that reserves the card height so the board doesn't jump. */
export function TradeHubSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading trade ideas" data-testid="trade-hub-skeleton">
      {[0, 1, 2].map((key) => (
        <div key={key} className="glass-surface flex flex-col gap-3 p-4" style={{ minHeight: "22rem" }}>
          <SkeletonBlock width="40%" height={16} />
          <SkeletonBlock width="65%" height={22} />
          <SkeletonBlock width="90%" height={14} />
          <SkeletonBlock width="100%" height={120} />
          <SkeletonBlock width="100%" height={44} />
        </div>
      ))}
    </div>
  );
}
