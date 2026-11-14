import { TradesTabBar } from "@/components/TradesTabBar";
import { InfoTip } from "@/components/InfoTip";
import { PageTitle } from "@/components/PageTitle";
import type { PastTradeOutcome, TradeOutcomeHistoryResponse } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { ToneBadge } from "@/components/ToneBadge";
import { AccentCard } from "@/components/AccentCard";
import { NetEdgeBar, TradeSwapGlyph } from "@/components/TradeOutcomeHeader";
import { VerdictCallout } from "@/components/VerdictCallout";
import {
  formatTradeHistoryDate,
  outcomeLabel,
  outcomeToneColorVar,
  toTradeAssets,
  verdictDetailText,
  verdictToneColorVar,
} from "@/lib/tradeHistoryPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";
import { EmptyState } from "@/components/EmptyState";
import { LeagueLinkStep } from "@/components/LeagueLinkStep";

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

  const accent = verdict ? verdictToneColorVar(verdict) : outcomeToneColorVar(outcome.outcome);
  const netPct = result && result.status === "ready" ? (result.value?.net_delta_pct ?? null) : null;

  return (
    <AccentCard accent={accent} className="gap-2">
      <div className="flex items-start gap-3">
        <TradeSwapGlyph color={accent} />
        <div className="flex flex-col min-w-0 flex-1">
          <h3 className="break-words" style={{ font: "var(--font-card-title)" }}>
            {partner}
          </h3>
          {date ? (
            <span className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
              {date}
            </span>
          ) : null}
        </div>
        <ToneBadge label={outcomeLabel(outcome.outcome)} color={outcomeToneColorVar(outcome.outcome)} />
      </div>

      {verdict && result ? (
        <VerdictCallout color={verdictToneColorVar(verdict)} label={result.verdict_label} detail={detailText} />
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
        <ExchangeSide label="You sent" dotColor="var(--color-danger)" assets={toTradeAssets(summary.send)} />
        <ExchangeSide label="You received" dotColor="var(--color-success)" assets={toTradeAssets(summary.receive)} />
      </div>
    </AccentCard>
  );
}

export function TradeHistoryContent({ data, leagueId, leagueName }: { data: TradeOutcomeHistoryResponse; leagueId?: string | null; leagueName?: string }) {
  return (
    <main className="page-shell">
      {leagueId ? <TradesTabBar leagueId={leagueId} leagueName={leagueName || "League"} active="trade_history" /> : null}
      <header className="flex flex-col gap-1">
        <PageTitle page="Trade History" />
        <div className="flex flex-col gap-1">
          <InfoTip label="How outcomes are read">
            Once a confirmed trade has had a few weeks to play out, we&apos;ll show a real before/after read here,
            using actual points scored and value trend, never a guess. Nothing here changes how trades are proposed or
            accepted.
          </InfoTip>
        </div>
      </header>

      {data.outcomes.length === 0 ? (
        <EmptyState title="No trade history yet. Confirm a trade to see it here.">
          <div className="mt-2">
            <LeagueLinkStep step="trade-analyzer" label="Analyze a trade" pickLabel="Pick a league to analyze a trade" variant="primary" />
          </div>
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-4">
          {data.outcomes.map((outcome) => (
            <TradeHistoryRow key={outcome.id} outcome={outcome} />
          ))}
        </div>
      )}
      <ValuesCredit />
    </main>
  );
}
