import { FreeLimitNote } from "@/components/FreeLimitNote";
import Link from "next/link";
import { ButtonLink } from "@/components/Button";
import { useMemo, useState } from "react";

import type { TradeHubResponse } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { EmptyState } from "@/components/EmptyState";
import { TradeHubFilters } from "@/components/TradeHubFilters";
import { filterTradeIdeas } from "@/lib/tradeHubFilters";
import { TradeHubHoldCard } from "@/components/TradeHubHoldCard";
import { TradeIdeaCardView } from "@/components/TradeIdeaCard";
import { TradesTabBar } from "@/components/TradesTabBar";
import { tradeHubReasonMessage } from "@/lib/tradeHubPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";

/**
 * Ports modules/trade_hub_ui.py's render_trade_idea_card (the "You Send /
 * You Get" summary card, heavily reworked across tonight's PRs #1050/#1057/
 * #1058/#1063/#1066/#1068) for Revision 3. Reads from the exact same
 * GET .../trade-hub endpoint mobile's TradeHubScreen.tsx already calls —
 * no duplicated idea-generation or scoring logic here, only presentation.
 * The card itself (TradeIdeaCardView) now lives in TradeIdeaCard.tsx
 * (Revision 17 extraction) since Trade Finder's results render the exact
 * same TradeIdea wire shape.
 *
 * Deliberately NOT covered, matching the quick-view/full-detail split
 * coridian_ drew on 2026-10-13 ("quick views should show identity +
 * headline verdict, full analysis behind the tap"): Trade Analyzer (a
 * different shape, verdict-driven rather than a ranked board — see
 * TradeAnalyzerContent.tsx), the strategy/evaluation-lens selectors (Trade
 * Hub's own setup row — this page uses the same retool/Dynasty defaults
 * GET .../trade-hub itself defaults to), and the share-to-propose / Trade
 * Outcomes flow (there's no in-app trade-submission API; that's a
 * PNG-export feature, not core page parity).
 */

/** Plain-English posture line (server: trade_hub_engine.posture_sentence).
 * Beginners get the term explained under it via the shared BeginnerHelp;
 * advanced users see just the sentence. */
function PostureLine({ sentence }: { sentence: string }) {
  return (
    <>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {sentence}
      </p>
      <BeginnerHelp term="tradeHubPosture" />
    </>
  );
}

export function TradeHubContent({
  leagueId,
  leagueName,
  data,
  lens = "Dynasty",
  highlightPlayerId,
}: {
  leagueId: string;
  leagueName: string;
  data: TradeHubResponse;
  /** The valuation lens these ideas were generated under — threaded down to
   * ShareTradeButton so its share-card fetch asks for the SAME idea the
   * board actually rendered (strategy/lens are both part of the server's
   * idea-identity cache key — see services/mobile_api_service.py's
   * GET .../trade-hub/{id}/share-card.png docstring). */
  lens?: string;
  /** Recommendation-compliance audit, Check 3 — a GM Plan/Dashboard trade
   * tile's named player (?playerId=, see gamePlanTileHref), threaded down so
   * whichever idea actually involves this player auto-expands, highlights,
   * and scrolls into view instead of leaving the user to re-find it among
   * every other idea on the board. Stale/absent ids simply match nothing. */
  highlightPlayerId?: string;
}) {
  const [filter, setFilter] = useState<{ impact: string | null; position: string | null }>({ impact: null, position: null });
  const visibleIdeas = useMemo(() => filterTradeIdeas(data.ideas, filter), [data.ideas, filter]);
  const notice = data.reason ? tradeHubReasonMessage(data.reason) : null;
  if (notice) {
    return (
      <main className="flex-1 flex flex-col gap-4 items-center justify-center px-4">
        <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_hub" />
        {data.hold ? (
          <div className="w-full max-w-3xl">
            <TradeHubHoldCard hold={data.hold} />
          </div>
        ) : (
          <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
            {notice}
          </p>
        )}
      </main>
    );
  }

  const entitlement = data.entitlement;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_hub" />
      <header className="flex flex-col gap-1">
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Ideas built around your roster.
        </p>
        <BeginnerHelp term="tradeHubIntro" />
        {data.posture_sentence ? <PostureLine sentence={data.posture_sentence} /> : null}
      </header>

      {entitlement ? (
        <FreeLimitNote
          kind="window"
          noun="trade ideas"
          limit={entitlement.free_limit}
          total={entitlement.approved_count}
          shown={entitlement.visible_count}
          isPremium={entitlement.is_premium}
        />
      ) : null}

      {data.hold ? <TradeHubHoldCard hold={data.hold} /> : null}

      {data.ideas.length > 0 ? <TradeHubFilters ideas={data.ideas} filter={filter} onChange={setFilter} /> : null}

      {data.ideas.length === 0 && data.hold ? (
        <Link href={`/trade-finder/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`} className="tap-link text-sm font-bold" style={{ color: "var(--color-accent)" }}>
          Build your own in Trade Finder →
        </Link>
      ) : data.ideas.length === 0 ? (
        <EmptyState
          title="No trade ideas right now"
          subtitle="Ideas appear when rosters move. Build your own in Trade Finder."
        >
          <Link href={`/trade-finder/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`} className="tap-link text-sm font-bold" style={{ color: "var(--color-accent)" }}>
            Open Trade Finder →
          </Link>
        </EmptyState>
      ) : visibleIdeas.length === 0 ? (
        <EmptyState
          title="No ideas match these filters"
          subtitle="Clear a filter to see the rest of the board."
          actionLabel="Show all"
          onAction={() => setFilter({ impact: null, position: null })}
        />
      ) : (
        <div className="flex flex-col gap-4">
          {visibleIdeas.map((idea, index) => {
            const highlighted = Boolean(
              highlightPlayerId &&
                [...idea.package.send, ...idea.package.receive].some((asset) => asset.player_id === highlightPlayerId),
            );
            return (
              <TradeIdeaCardView
                key={`${idea.partner_team_name}-${idea.recommendation_id ?? index}`}
                idea={idea}
                leagueId={leagueId}
                strategy={data.team_strategy}
                lens={lens}
                highlighted={highlighted}
              />
            );
          })}
        </div>
      )}

      {entitlement && entitlement.hidden_count > 0 ? (
        <div
          className="p-4 flex flex-col gap-2 premium-glow-card"
          style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-premium)" }}
        >
          <p className="text-sm font-bold">
            {entitlement.hidden_count} more trade idea{entitlement.hidden_count === 1 ? "" : "s"} available on Premium.
          </p>
          <ButtonLink href="/premium" variant="premium" size="sm">
            Upgrade →
          </ButtonLink>
        </div>
      ) : null}
      <ValuesCredit />
    </main>
  );
}
