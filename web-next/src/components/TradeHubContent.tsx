import Link from "next/link";

import type { TradeHubResponse } from "@/lib/api";
import { TradeIdeaCardView } from "@/components/TradeIdeaCard";
import { TradesTabBar } from "@/components/TradesTabBar";
import { tradeHubReasonMessage } from "@/lib/tradeHubPresentation";

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

export function TradeHubContent({
  leagueId,
  leagueName,
  data,
}: {
  leagueId: string;
  leagueName: string;
  data: TradeHubResponse;
}) {
  const notice = data.reason ? tradeHubReasonMessage(data.reason) : null;
  if (notice) {
    return (
      <main className="flex-1 flex flex-col gap-4 items-center justify-center px-4">
        <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_hub" />
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {notice}
        </p>
      </main>
    );
  }

  const entitlement = data.entitlement;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_hub" />
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Trade Hub
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Trade ideas built around your roster — You Send / You Get, ranked by fit.
        </p>
      </header>

      {data.ideas.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No trade ideas right now. Check back after rosters move this week.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {data.ideas.map((idea, index) => (
            <TradeIdeaCardView key={`${idea.partner_team_name}-${index}`} idea={idea} />
          ))}
        </div>
      )}

      {entitlement && entitlement.hidden_count > 0 ? (
        <div
          className="p-4 flex flex-col gap-2"
          style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-action)" }}
        >
          <p className="text-sm font-bold">
            {entitlement.hidden_count} more trade idea{entitlement.hidden_count === 1 ? "" : "s"} available on Premium.
          </p>
          <Link href="/premium" className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
            Upgrade →
          </Link>
        </div>
      ) : null}
    </main>
  );
}
