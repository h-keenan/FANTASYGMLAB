import { useState } from "react";
import type { TradeHubResponse, TradeIdea } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { TradesTabBar } from "@/components/TradesTabBar";
import { ValueRing } from "@/components/ValueRing";
import { streamlitPageUrl } from "@/lib/streamlitLink";
import {
  LOW_CONFIDENCE_USER_NOTE,
  categoryColor,
  confidenceLevel,
  confidenceRingPercent,
  fairnessBandColor,
  formatTradeGain,
  impactTagConfig,
  levelToRingTone,
  realismLevel,
  realismRingPercent,
  tradeHubReasonMessage,
} from "@/lib/tradeHubPresentation";

/**
 * Ports modules/trade_hub_ui.py's render_trade_idea_card (the "You Send /
 * You Get" summary card, heavily reworked across tonight's PRs #1050/#1057/
 * #1058/#1063/#1066/#1068) for Revision 3. Reads from the exact same
 * GET .../trade-hub endpoint mobile's TradeHubScreen.tsx already calls —
 * no duplicated idea-generation or scoring logic here, only presentation.
 *
 * Deliberately NOT covered, matching the quick-view/full-detail split
 * coridian_ drew on 2026-10-13 ("quick views should show identity +
 * headline verdict, full analysis behind the tap"): Trade Finder and Trade
 * Analyzer (separate tabs on mobile, still Streamlit-only here), the
 * strategy/evaluation-lens selectors (Trade Hub's own setup row — this page
 * uses the same retool/Dynasty defaults GET .../trade-hub itself defaults
 * to), and the share-to-propose / Trade Outcomes flow (there's no in-app
 * trade-submission API; that's a PNG-export feature, not core page parity).
 */

function ReasoningTags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag) => (
        <span
          key={tag}
          className="px-1.5 py-0.5 text-xs font-bold"
          style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

function TradeIdeaCardView({ idea }: { idea: TradeIdea }) {
  const [expanded, setExpanded] = useState(false);
  const gain = idea.trade_gain;
  const deltaText = formatTradeGain(gain);
  const deltaColor = gain > 0 ? "var(--color-success)" : gain < 0 ? "var(--color-danger)" : "var(--color-text-secondary)";
  const accent = categoryColor(idea.category);
  const impact = impactTagConfig(idea.impact_tag);
  const isLowConfidence = idea.confidence_label.trim().toLowerCase() === "low";
  const landedNames = (idea.landed_gm_target_player_ids || [])
    .map((playerId) => idea.package.receive.find((asset) => asset.player_id === playerId)?.name)
    .filter((name): name is string => Boolean(name));

  const confidenceLvl = confidenceLevel(idea.confidence_label);
  const realismLvl = realismLevel(idea.market_realism_label);

  return (
    <article
      className="flex flex-col gap-3 p-4"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
        borderLeft: `3px solid ${accent}`,
        boxShadow: "var(--shadow-card)",
      }}
    >
      {idea.category || impact ? (
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <span
            className="px-1.5 py-0.5 uppercase text-xs font-extrabold"
            style={{
              color: accent,
              background: "var(--color-surface-muted)",
              letterSpacing: "var(--letter-spacing-badge)",
            }}
          >
            {idea.category}
          </span>
          {impact ? (
            <span
              className="px-1.5 py-0.5 uppercase text-xs font-extrabold"
              style={{ color: impact.color, border: `1px solid ${impact.color}80`, letterSpacing: "var(--letter-spacing-badge)" }}
            >
              {impact.label}
            </span>
          ) : null}
        </div>
      ) : null}

      {landedNames.length > 0 ? (
        <p className="text-xs font-bold" style={{ color: "var(--color-premium)" }}>
          Lands your target: {landedNames.join(", ")}
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-base font-extrabold truncate" style={{ color: "var(--color-text-primary)" }}>
          {idea.partner_team_name}
        </h3>
        {idea.value_edge_band ? (
          <span
            className="px-1.5 py-0.5 text-xs font-bold uppercase shrink-0"
            style={{ color: fairnessBandColor(idea.value_edge_band), border: `1px solid ${fairnessBandColor(idea.value_edge_band)}` }}
          >
            {idea.value_edge_band}
          </span>
        ) : null}
      </div>
      {idea.partner_team_archetype_label ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {idea.partner_team_archetype_label}
        </span>
      ) : null}

      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline gap-2">
          <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Balance
          </span>
          <span className="text-2xl font-black" style={{ color: deltaColor, fontVariantNumeric: "tabular-nums" }}>
            {deltaText}
          </span>
        </div>
        <LeanBarMeter sendScore={idea.send_score} receiveScore={idea.receive_score} />
      </div>

      {/* Width-fill fix (PR #1050, reconfirmed here): minmax(0,1fr) on both
          exchange columns, never max-content/auto-sized — the same
          dead-space-on-the-right bug that hit .dg-gp-trade-visual and
          .dg-trade-matchup in Streamlit three separate times tonight. */}
      <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_1.5rem_minmax(0,1fr)] gap-3 items-start">
        <ExchangeSide label="You send" dotColor="var(--color-danger)" assets={idea.package.send} />
        <div
          className="hidden sm:flex items-center justify-center text-xs font-bold uppercase self-stretch"
          style={{ color: "var(--color-accent)" }}
          aria-hidden="true"
        >
          FOR
        </div>
        <ExchangeSide label="You get" dotColor="var(--color-success)" assets={idea.package.receive} />
      </div>

      {isLowConfidence ? (
        <p className="text-xs" style={{ color: "var(--color-warning)" }}>
          {LOW_CONFIDENCE_USER_NOTE}
        </p>
      ) : null}

      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="self-start text-sm font-bold"
        style={{ color: "var(--color-accent)" }}
        aria-expanded={expanded}
      >
        {expanded ? "Hide details" : "Review package →"}
      </button>

      {expanded ? (
        <div className="flex flex-col gap-3 pt-2" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
          {idea.rationale ? (
            <div className="flex flex-col gap-1">
              <span className="text-xs uppercase font-bold" style={{ color: "var(--color-information)" }}>
                Why this works
              </span>
              <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {idea.rationale}
              </p>
            </div>
          ) : null}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex flex-col items-center gap-1">
              <ValueRing
                percent={confidenceRingPercent(idea.confidence_label)}
                tone={levelToRingTone(confidenceLvl)}
                display={`${confidenceRingPercent(idea.confidence_label)}%`}
                ariaLabel={`Confidence: ${idea.confidence_label}`}
                size="sm"
              />
              <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                Confidence · {idea.confidence_label}
              </span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <ValueRing
                percent={realismRingPercent(idea.market_realism_label)}
                tone={levelToRingTone(realismLvl)}
                display={`${realismRingPercent(idea.market_realism_label)}%`}
                ariaLabel={`Market realism: ${idea.market_realism_label}`}
                size="sm"
              />
              <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                Realism · {idea.market_realism_label}
              </span>
            </div>
          </div>
          <ReasoningTags tags={idea.reasoning_tags} />
        </div>
      ) : null}
    </article>
  );
}

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
          <a href={streamlitPageUrl("premium")} className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
            Upgrade →
          </a>
        </div>
      ) : null}
    </main>
  );
}
