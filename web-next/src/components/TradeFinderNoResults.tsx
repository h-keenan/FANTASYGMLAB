import { EmptyState } from "@/components/EmptyState";
import { ToneBadge } from "@/components/ToneBadge";
import { TradeIdeaCardView } from "@/components/TradeIdeaCard";
import type { TradeFinderClosestIdea, TradeFinderSearch } from "@/lib/api";

/**
 * Trade Finder's "nothing realistic" state. A bare "no trades found" gave the
 * same dead end whether nothing was priced near the selection, every partner
 * declined on roster fit, or the search itself failed. This shows the measured
 * reason (`search`, from modules.trade_ideas.finder_search_payload) and the
 * closest non-realistic packages, each labelled "Stretch" with what stops it
 * from being realistic. Mobile mirrors it in TradeFinderNoResults.tsx.
 */
export function TradeFinderNoResults({
  search,
  closest,
  leagueId,
  lens,
  onRetry,
}: {
  search?: TradeFinderSearch;
  closest?: TradeFinderClosestIdea[];
  leagueId: string;
  lens: string;
  onRetry?: () => void;
}) {
  if (search?.status === "error") {
    return (
      <EmptyState
        title="The search hit a problem."
        subtitle={search.headline}
        actionLabel={onRetry ? "Try again" : undefined}
        onAction={onRetry}
      />
    );
  }

  const reasons = (search?.reasons ?? []).filter((reason) => !(search?.headline ?? '').includes(reason.text));
  const options = closest ?? [];
  return (
    <div className="flex flex-col gap-4" data-testid="trade-finder-no-results">
      <EmptyState
        title="No realistic trades found for this selection right now."
        subtitle={search?.headline || undefined}
      >
        {reasons.length > 0 ? (
          <ul className="flex flex-col gap-1 mt-2 list-disc pl-4 text-xs" style={{ color: "var(--color-text-muted)" }}>
            {reasons.map((reason) => (
              <li key={reason.code}>{reason.text}</li>
            ))}
          </ul>
        ) : null}
      </EmptyState>
      {options.length > 0 ? (
        <section className="flex flex-col gap-3" aria-label="Closest options">
          <span
            className="text-xs uppercase font-bold"
            style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
          >
            Closest options (stretch)
          </span>
          {options.map((idea, index) => (
            <div key={`${idea.partner_team_name}-${index}`} className="flex flex-col gap-2" data-testid="trade-finder-closest">
              <div className="flex items-start gap-2">
                <ToneBadge label={idea.finder_note?.label ?? "Stretch"} color="var(--color-warning)" />
                {idea.finder_note?.reason ? (
                  <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {idea.finder_note.reason}
                  </p>
                ) : null}
              </div>
              <TradeIdeaCardView idea={idea} leagueId={leagueId} strategy="retool" lens={lens} />
            </div>
          ))}
        </section>
      ) : null}
    </div>
  );
}
