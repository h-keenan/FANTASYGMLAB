import Link from "next/link";
import { useState } from "react";

import type { TradeHubResponse } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
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

/** Backend strategy values are snake_case engine tokens (e.g.
 * "fringe_contender") — title-case for display, same approach
 * formatGamePlanCategory already uses for a different snake_case field. */
function formatStrategyLabel(strategy: string): string {
  return strategy
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

// coridian_, screenshot: "it says values reflect a retool strategy, yet
// there's nowhere to change that strategy, and there's no explanation of
// what retool means or dynasty or whatever else young contender... people's
// natural inclination when they don't know what something is on a phone is
// probably to tap it." Plain-language versions of the same five age-curve
// buckets modules/trade_hub_engine.py's apply_strategy_age_curve actually
// applies — not invented copy, just that function's real behavior in
// words. Changing the strategy itself stays out of scope here (it's driven
// by Team Situation on this page, a deliberate separate control surface,
// not a Trade-Hub-local setting) — this fix is the missing explanation.
const STRATEGY_EXPLANATIONS: Record<string, string> = {
  contender: "Values lean toward players in their prime (25-30) who help you win now, and slightly discount very young players and aging running backs.",
  fringe_contender: "A lighter version of Contender — still leans toward players who help you win soon, without discounting youth as much.",
  retool: "A middle ground: values tilt toward younger players (25 and under) while still crediting players through their late 20s.",
  rebuild: "Values lean heavily toward young players and discount aging ones, since the plan is to build around players who'll be good years from now.",
  tank: "The most aggressive lean toward youth — older players are discounted the most, prioritizing future assets over today's roster.",
};

function StrategyExplainer({ strategy }: { strategy: string }) {
  const [open, setOpen] = useState(false);
  const explanation = STRATEGY_EXPLANATIONS[strategy];

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="text-xs text-left underline self-start"
        style={{ color: "var(--color-text-muted)" }}
      >
        Values here reflect a <strong>{formatStrategyLabel(strategy)}</strong> strategy — they may differ
        slightly from Waivers, Dashboard, or Player Quick View. What does this mean?
      </button>
      {open ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {explanation ||
            "This strategy nudges trade values based on player age, favoring whichever players fit your current team-building plan."}{" "}
          Set under Team Situation, not here.
        </p>
      ) : null}
    </div>
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
        <BeginnerHelp term="tradeHubIntro" />
        {/* Logic/valuation audit, 2026-10-18: Trade Hub applies a team-
            strategy age-curve adjustment to player value that Waivers/
            Dashboard/PQV's plain valuation pipeline doesn't — the same
            player can show a different number there than here, with
            nothing explaining why. This names the strategy these values
            were generated under instead of leaving that silent. */}
        {data.team_strategy ? <StrategyExplainer strategy={data.team_strategy} /> : null}
      </header>

      {data.ideas.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No trade ideas right now. Check back after rosters move this week.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {data.ideas.map((idea, index) => {
            const highlighted = Boolean(
              highlightPlayerId &&
                [...idea.package.send, ...idea.package.receive].some((asset) => asset.player_id === highlightPlayerId),
            );
            return (
              <TradeIdeaCardView
                key={`${idea.partner_team_name}-${index}`}
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
