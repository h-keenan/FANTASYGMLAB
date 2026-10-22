import { useEffect, useRef, useState } from "react";
import { api, type TradeIdea } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { TeamAvatar } from "@/components/TeamAvatar";
import { TradeCategoryGlyph } from "@/components/TradeCategoryGlyph";
import { ValueRing } from "@/components/ValueRing";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { shareImageOrText } from "@/lib/shareImage";
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
  tradeIdeaShareRecord,
  tradeIdeaShareText,
} from "@/lib/tradeHubPresentation";

/**
 * Shares the branded trade card PNG (app/share-card/trade, drawn by
 * web-next from the app's design tokens) via the Files-capable Web Share
 * API when this idea/league/browser supports it, falling back to the text
 * share, then a clipboard copy (lib/shareImage).
 */
export function ShareTradeButton({
  idea,
  leagueId,
  strategy = "retool",
  lens = "Dynasty",
}: {
  idea: TradeIdea;
  /** Needed to fetch the branded share-card PNG — omitted (e.g. in an
   * older caller) simply skips straight to the text-only share path. */
  leagueId?: string;
  strategy?: string;
  lens?: string;
}) {
  const [copied, setCopied] = useState(false);
  const [preparingImage, setPreparingImage] = useState(false);

  // Records the share for the later "Did this trade happen?" prompt, same
  // as mobile's TradeSharePreviewModal.recordShare: fire-and-forget, once
  // per completed share (no dedupe, as on mobile; the prompt's "Didn't
  // send" answer covers a share that never really went out). Skipped
  // without a leagueId, since the endpoint is league-scoped.
  const recordShare = () => {
    if (!leagueId) return;
    void api.recordTradeShare(leagueId, tradeIdeaShareRecord(idea, lens)).catch(() => {});
  };

  const onShare = async () => {
    const recommendationId = idea.recommendation_id;
    const outcome = await shareImageOrText({
      fetchImage:
        leagueId && recommendationId
          ? () => api.getTradeHubIdeaShareCardBlob(leagueId, recommendationId, strategy, lens)
          : undefined,
      filename: `fantasydesk-trade-${recommendationId ?? "idea"}.png`,
      text: tradeIdeaShareText(idea),
      title: `Trade idea vs. ${idea.partner_team_name}`,
      onPreparingImage: setPreparingImage,
    });
    if (outcome === "shared-image" || outcome === "shared-text" || outcome === "copied") recordShare();
    if (outcome === "copied") {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      type="button"
      onClick={onShare}
      disabled={preparingImage}
      // coridian_, 2026-10-18: "The share trade button is still just
      // text" — plain colored text with no button chrome at all (no
      // border/background), indistinguishable from a navigation link.
      // Same small bordered-pill treatment the value-edge badge right
      // beside it already uses in this row.
      className="px-1.5 py-0.5 text-xs font-bold uppercase shrink-0"
      style={{ color: "var(--color-accent)", border: "1px solid var(--color-accent)" }}
    >
      {preparingImage ? "Preparing…" : copied ? "Copied!" : "Share"}
    </button>
  );
}

/**
 * The "You Send / You Get" trade-idea card — ports modules/trade_hub_ui.py's
 * render_trade_idea_card. Extracted out of TradeHubContent.tsx (Revision 17
 * CSS/redundancy cleanup pass) so Trade Finder's results
 * (TradeFinderContent.tsx) can render the exact same card for the exact same
 * wire shape (both .../trade-hub and .../trade-finder serialize through
 * modules.trade_hub_engine's shared card projection) instead of forking a
 * second copy of ~180 lines of card markup. Trade Hub is still the only
 * caller that passes a card with `category`/`impact_tag`/
 * `landed_gm_target_player_ids` populated with real content — Trade Finder's
 * engine call doesn't score against a GM Target list or a passive-board
 * category taxonomy, so those sections simply don't render for it, exactly
 * as they wouldn't render for any idea where the server sends empty values.
 */

export function ReasoningTags({ tags }: { tags: string[] }) {
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

export function TradeIdeaCardView({
  idea,
  leagueId,
  strategy,
  lens,
  highlighted = false,
}: {
  idea: TradeIdea;
  leagueId?: string;
  strategy?: string;
  lens?: string;
  /** Recommendation-compliance audit, Check 3 — true when a GM Plan/
   * Dashboard trade tile named this exact idea (TradeHubContent matches its
   * ?playerId= against this idea's give/get package). Auto-expands the
   * package, scrolls it into view, and marks it, instead of leaving the
   * user to find it among every other idea on the board. */
  highlighted?: boolean;
}) {
  const [expanded, setExpanded] = useState(highlighted);
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (highlighted && ref.current && typeof ref.current.scrollIntoView === "function") {
      ref.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlighted]);
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
  const copy = useExperienceCopy();

  return (
    <article
      ref={ref}
      data-highlighted={highlighted ? "true" : undefined}
      className="glass-surface flex flex-col gap-3 p-4"
      style={{
        borderLeft: `var(--border-width-semantic) solid ${accent}`,
        ...(highlighted ? { outline: "2px solid var(--color-accent)", outlineOffset: "2px" } : {}),
      }}
    >
      {idea.category || impact ? (
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <span
            className="flex items-center gap-1 px-1.5 py-0.5 uppercase text-xs font-extrabold"
            style={{
              color: accent,
              background: "var(--color-surface-muted)",
              letterSpacing: "var(--letter-spacing-badge)",
            }}
          >
            <TradeCategoryGlyph category={idea.category} />
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
      <BeginnerHelp text={copy.impactTagHelp(idea.impact_tag)} />

      {landedNames.length > 0 ? (
        <p className="text-xs font-bold" style={{ color: "var(--color-premium)" }}>
          Lands your target: {landedNames.join(", ")}
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <TeamAvatar avatarUrl={idea.partner_team_avatar_url} size={24} />
          <h3 className="text-base font-extrabold truncate" style={{ color: "var(--color-text-primary)" }}>
            {idea.partner_team_name}
          </h3>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {idea.value_edge_band ? (
            <span
              className="px-1.5 py-0.5 text-xs font-bold uppercase"
              style={{ color: fairnessBandColor(idea.value_edge_band), border: `1px solid ${fairnessBandColor(idea.value_edge_band)}` }}
            >
              {idea.value_edge_band}
            </span>
          ) : null}
          <ShareTradeButton idea={idea} leagueId={leagueId} strategy={strategy} lens={lens} />
        </div>
      </div>
      {idea.partner_team_archetype_label ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {idea.partner_team_archetype_label}
        </span>
      ) : null}

      <div className="flex items-baseline gap-2">
        <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Balance
        </span>
        <span className="text-2xl font-black" style={{ color: deltaColor, fontVariantNumeric: "tabular-nums" }}>
          {deltaText}
        </span>
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

      {/* Discrepancy bar moved below the give/get package (coridian_,
          2026-10-16: "I think the overall trade value discrepancy bar
          should be underneath the trade, like underneath the players and
          picks") — previously sat directly under the Balance figure, above
          the package. */}
      <LeanBarMeter sendScore={idea.send_score} receiveScore={idea.receive_score} />
      <BeginnerHelp term="ideaBalance" />

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
                {copy.label("ideaRealism", "Realism")} · {idea.market_realism_label}
              </span>
            </div>
          </div>
          <BeginnerHelp term="ideaConfidence" />
          <BeginnerHelp term="ideaRealism" />
          <ReasoningTags tags={idea.reasoning_tags} />
        </div>
      ) : null}
    </article>
  );
}
