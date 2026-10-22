import type { PastTradeOutcome, TradeOutcomeHistoryResponse } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { ToneBadge } from "@/components/ToneBadge";
import { VerdictCallout } from "@/components/VerdictCallout";
import {
  formatTradeHistoryDate,
  outcomeLabel,
  outcomeToneColorVar,
  toTradeAssets,
  verdictDetailText,
  verdictToneColorVar,
} from "@/lib/tradeHistoryPresentation";

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

  return (
    <article className="glass-surface flex flex-col gap-2 p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col min-w-0">
          <h3 className="truncate" style={{ font: "var(--font-card-title)" }}>
            {partner}
          </h3>
          {date ? (
            <span className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
              {date}
            </span>
          ) : null}
        </div>
        <ToneBadge variant="pill" label={outcomeLabel(outcome.outcome)} color={outcomeToneColorVar(outcome.outcome)} />
      </div>

      {verdict && result ? (
        <VerdictCallout color={verdictToneColorVar(verdict)} label={result.verdict_label} detail={detailText} />
      ) : null}

      <div className="grid grid-cols-2 gap-4 mt-1">
        <ExchangeSide label="You sent" dotColor="var(--color-danger)" assets={toTradeAssets(summary.send)} />
        <ExchangeSide label="You received" dotColor="var(--color-success)" assets={toTradeAssets(summary.receive)} />
      </div>
    </article>
  );
}

export function TradeHistoryContent({ data }: { data: TradeOutcomeHistoryResponse }) {
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Trade History
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>Did it work out?</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Trades you&apos;ve confirmed you made. Once a confirmed trade has had a few weeks to play out, we&apos;ll
          show a real before/after read here, using actual points scored and value trend, never a guess. Nothing
          here changes how trades are proposed or accepted.
        </p>
      </header>

      {data.outcomes.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No trade history yet. Answer &quot;Did this trade happen?&quot; the next time it comes up, and it&apos;ll
          show up here, along with how it worked out once there&apos;s enough real data.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {data.outcomes.map((outcome) => (
            <TradeHistoryRow key={outcome.id} outcome={outcome} />
          ))}
        </div>
      )}
    </main>
  );
}
