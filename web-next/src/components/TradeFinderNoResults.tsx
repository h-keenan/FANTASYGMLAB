import { EmptyState } from "@/components/EmptyState";
import { ToneBadge } from "@/components/ToneBadge";
import { TradeIdeaCardView } from "@/components/TradeIdeaCard";
import type { TradeFinderClosestIdea, TradeFinderNote, TradeFinderSearch } from "@/lib/api";

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
  const blocked = search?.status === "selected_assets_blocked";
  return (
    <div className="flex flex-col gap-4" data-testid="trade-finder-no-results">
      <EmptyState
        title={
          blocked
            ? "We couldn't build a trade with everything you selected."
            : "No realistic trades found for this selection right now."
        }
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
      <TradeFinderClosestSection options={options} leagueId={leagueId} lens={lens} />
    </div>
  );
}

/** One plain-English line above Trade Finder results saying what every
 * package contains (or why nothing does). Never blank: the headline comes from
 * modules.trade_ideas.finder_search_payload. */
export function TradeFinderSummary({ search }: { search?: TradeFinderSearch }) {
  if (!search?.headline) return null;
  return (
    <p
      className="text-sm"
      style={{ color: "var(--color-text-secondary, var(--color-text-muted))" }}
      data-testid="trade-finder-summary"
    >
      {search.headline}
    </p>
  );
}

/** Near misses, stretches (overpay) and "without X" alternatives. Each card
 * carries a label and one honest reason, so it is never mistaken for a result
 * that includes everything the user selected. */
export function TradeFinderClosestSection({
  options,
  leagueId,
  lens,
}: {
  options: TradeFinderClosestIdea[];
  leagueId: string;
  lens: string;
}) {
  if (options.length === 0) return null;
  return (
    <section className="flex flex-col gap-3" aria-label="Closest options">
      <span
        className="text-xs uppercase font-bold"
        style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        Closest options (stretch)
      </span>
      {options.map((idea, index) => (
        <div key={`${idea.partner_team_name}-${index}`} className="flex flex-col gap-2" data-testid="trade-finder-closest">
          <TradeFinderNoteRow note={idea.finder_note} fallbackLabel="Stretch" />
          <TradeIdeaCardView idea={idea} leagueId={leagueId} strategy="retool" lens={lens} />
        </div>
      ))}
    </section>
  );
}

/** Label + reason above a Trade Finder card ("We added", "Overpay",
 * "Without Aaron Jones", "Stretch"). */
export function TradeFinderNoteRow({
  note,
  fallbackLabel,
}: {
  note?: TradeFinderNote;
  fallbackLabel?: string;
}) {
  if (!note && !fallbackLabel) return null;
  const tone = note?.stage === "we_added" ? "var(--color-accent)" : "var(--color-warning)";
  return (
    <div className="flex items-start gap-2" data-testid="trade-finder-note">
      <ToneBadge label={note?.label ?? fallbackLabel ?? ""} color={tone} />
      {note?.reason ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {note.reason}
        </p>
      ) : null}
    </div>
  );
}
