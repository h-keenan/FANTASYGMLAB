import { TradesTabBar } from "@/components/TradesTabBar";
import { PageTitle } from "@/components/PageTitle";
import type { PastTradeOutcome, TradeOutcomeHistoryResponse } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { TradeSummaryRow } from "@/components/ui/TradeSummaryRow";
import { isPickAsset, tradeOutcomeChips, tradeValueDelta, tradeVerdictBadge } from "@/lib/tradeOutcomeChips";
import { abbreviatePlayerName } from "@/lib/formatPlayerName";
import { tradeIdeaNamesText } from "@/lib/tradeIdeaSummary";
import { NetEdgeBar } from "@/components/TradeOutcomeHeader";
import { VerdictCallout } from "@/components/VerdictCallout";
import {
  formatTradeHistoryDate,
  outcomeLabel,
  toTradeAssets,
  verdictDetailText,
} from "@/lib/tradeHistoryPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";
import { EmptyState } from "@/components/EmptyState";
import { LeagueLinkStep } from "@/components/LeagueLinkStep";
import { TrackRecordModule } from "@/components/TrackRecordModule";
import { tradePointsLine } from "@/lib/trackRecordView";

/**
 * Ports modules/trade_outcomes_page.py's render_trade_history_page — the
 * quiet "did this trade actually work out?" follow-up (PR #972/#974), a
 * standalone GM_TOOLS destination distinct from Trade Hub/Finder/Analyzer.
 * Reachable on mobile via a header icon inside TradesScreen or via More ->
 * Your Team (mobile/src/screens/TradeHistoryScreen.tsx); here it's linked
 * the same two ways: a header link beside TradesTabBar, and Dashboard's
 * Explore grid.
 *
 * Free feature (no Premium gate — mirrors mobile and GET
 * /v1/trade-outcomes/history, neither of which gate on entitlement). No new
 * valuation or grading math: every row already comes from
 * modules.trade_outcome_results's standalone cron sweep, read back verbatim.
 */

function TradeHistoryRow({ outcome }: { outcome: PastTradeOutcome }) {
  const summary = outcome.trade_summary;
  const partner = outcome.partner_team_name || summary.partner_team_name || "your trade partner";
  const date = formatTradeHistoryDate(outcome.shared_at);

  // Only a confirmed ('yes') trade can ever carry a real computed result —
  // same gate services/mobile_api_service.py's _project_trade_outcome_history
  // and mobile's TradeHistoryScreen both apply. A "ready" status is the only
  // one with an actual verdict; "insufficient_data" (or nothing computed
  // yet) shows no verdict badge/body at all, never a fake "checking..."
  // placeholder.
  const result = outcome.outcome === "yes" ? outcome.result_summary : null;
  const verdict = result && result.status === "ready" ? result.verdict : null;
  const detailText = result ? verdictDetailText(result) : "";

  const netPct = result && result.status === "ready" ? (result.value?.net_delta_pct ?? null) : null;
  // Per-trade outcome card: real PPR points for you since the trade (free; the sweep already computed it).
  const pointsLine = outcome.outcome === "yes" ? tradePointsLine(result) : null;
  const netPts = result && result.status === "ready" ? (result.production?.net_points_ppr ?? null) : null;

  const sentAssets = toTradeAssets(summary.send);
  const receivedAssets = toTradeAssets(summary.receive);
  const sent = tradeIdeaNamesText(sentAssets.map((asset) => abbreviatePlayerName(asset.name)));
  const received = tradeIdeaNamesText(receivedAssets.map((asset) => abbreviatePlayerName(asset.name)));
  const people = (assets: typeof sentAssets, side: string) => assets.map((a, i) => ({ key: `${side}${i}`, playerId: a.player_id ?? null, name: a.name ?? "", position: a.position, isPick: isPickAsset(a) }));

  return (
    <TradeSummaryRow
      testId={`trade-history-${outcome.id}`}
      partner={partner}
      send={people(sentAssets, "s")}
      receive={people(receivedAssets, "r")}
      swapText={sent && received ? `${sent} for ${received}` : ""}
      chips={tradeOutcomeChips({ outcomeLabel: outcomeLabel(outcome.outcome), netPts })}
      verdict={result && verdict ? tradeVerdictBadge(verdict, result.verdict_label) : null}
      delta={tradeValueDelta(netPct)}
      date={date}
    >
      {pointsLine ? (
        <p className="m-0 text-sm font-semibold" style={{ color: "var(--color-text-primary)" }} data-testid="trade-points-line">
          {pointsLine}
        </p>
      ) : null}
      {verdict && result ? (
        <VerdictCallout color="var(--color-text-secondary)" label={result.verdict_label} detail={detailText} />
      ) : null}
      {netPct !== null ? (
        <NetEdgeBar
          netPct={netPct}
          label={
            <>
              <span>Partner ahead</span>
              <span>You ahead</span>
            </>
          }
        />
      ) : null}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-1">
        <ExchangeSide label="You sent" dotColor="var(--color-text-muted)" assets={sentAssets} />
        <ExchangeSide label="You received" dotColor="var(--color-text-muted)" assets={receivedAssets} />
      </div>
    </TradeSummaryRow>
  );
}

export function TradeHistoryContent({ data, leagueId, leagueName }: { data: TradeOutcomeHistoryResponse; leagueId?: string | null; leagueName?: string }) {
  return (
    <main className="page-shell">
      {leagueId ? <TradesTabBar leagueId={leagueId} leagueName={leagueName || "League"} active="trade_history" /> : null}
      <header className="flex flex-col gap-1">
        <PageTitle
          page="Trade History"
          info={
            <p>
              Once a confirmed trade has had a few weeks to play out, we&apos;ll show a real before/after read here, using actual points scored and value trend,
              never a guess. Nothing here changes how trades are proposed or accepted.
            </p>
          }
        />
      </header>

      {data.outcomes.length === 0 ? (
        <EmptyState title="No trade history yet. Confirm a trade to see it here.">
          <div className="mt-2">
            <LeagueLinkStep step="trade-analyzer" label="Analyze a trade" pickLabel="Pick a league to analyze a trade" variant="primary" />
          </div>
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-4">
          <TrackRecordModule />
          {data.outcomes.map((outcome) => (
            <TradeHistoryRow key={outcome.id} outcome={outcome} />
          ))}
        </div>
      )}
      <ValuesCredit />
    </main>
  );
}
