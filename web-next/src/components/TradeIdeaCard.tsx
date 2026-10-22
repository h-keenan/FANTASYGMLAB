import { AccentCard } from "@/components/AccentCard";
import { ManagerTendenciesCard } from "@/components/ManagerTendenciesCard";
import { useEffect, useRef, useState } from "react";
import { api, type TradeIdea } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { ToneBadge } from "@/components/ToneBadge";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { TeamAvatar } from "@/components/TeamAvatar";
import { TradeCategoryGlyph } from "@/components/TradeCategoryGlyph";
import { ValueRing } from "@/components/ValueRing";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { shareImageOrText } from "@/lib/shareImage";
import { ideaTags, shortReason } from "@/lib/tradeHubFilters";
import {
  LOW_CONFIDENCE_USER_NOTE,
  categoryColor,
  confidenceLevel,
  confidenceRingPercent,
  fairnessBandColor,
  formatTradeGain,
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
      className="inline-flex flex-1 items-center justify-center gap-1.5 px-3 text-sm font-bold"
      style={{
        color: "var(--color-accent)",
        border: "1px solid var(--color-accent)",
        background: "transparent",
        minHeight: "2.75rem",
      }}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" />
        <path d="M16 6l-4-4-4 4" />
        <path d="M12 2v13" />
      </svg>
      {preparingImage ? "Preparing…" : copied ? "Copied!" : "Share Trade"}
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
  const isLowConfidence = idea.confidence_label.trim().toLowerCase() === "low";
  const landedNames = (idea.landed_gm_target_player_ids || [])
    .map((playerId) => idea.package.receive.find((asset) => asset.player_id === playerId)?.name)
    .filter((name): name is string => Boolean(name));

  const confidenceLvl = confidenceLevel(idea.confidence_label);
  const realismLvl = realismLevel(idea.market_realism_label);
  const copy = useExperienceCopy();

  const tags = ideaTags(idea);
  const reason = shortReason(idea.rationale);
  const moreReason = (idea.rationale || "").trim().slice(reason.length).trim();
  const sendTotal = Math.round(idea.send_score || 0).toLocaleString();
  const receiveTotal = Math.round(idea.receive_score || 0).toLocaleString();

  return (
    <AccentCard
      accent={accent}
      ref={ref}
      data-highlighted={highlighted ? "true" : undefined}
      style={highlighted ? { outline: "2px solid var(--color-accent)", outlineOffset: "2px" } : undefined}
    >
      {tags.length > 0 ? (
        <div className="flex items-center gap-2 flex-wrap">
          {tags.map((tag) => (
            <span
              key={tag.label}
              className="flex items-center gap-1 px-1.5 py-0.5 uppercase text-xs font-extrabold"
              style={{
                color: tag.color,
                background: "var(--color-surface-muted)",
                letterSpacing: "var(--letter-spacing-badge)",
              }}
            >
              {tag.kind === "category" ? <TradeCategoryGlyph category={idea.category} /> : null}
              {tag.label}
            </span>
          ))}
        </div>
      ) : null}
      <BeginnerHelp text={copy.impactTagHelp(idea.impact_tag)} />

      {landedNames.length > 0 ? (
        <p className="text-xs font-bold" style={{ color: "var(--color-premium)" }}>
          Lands your target: {landedNames.join(", ")}
        </p>
      ) : null}

      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col min-w-0 gap-0.5">
          <div className="flex items-center gap-2 min-w-0">
            <TeamAvatar avatarUrl={idea.partner_team_avatar_url} size={24} />
            <h3 className="text-lg font-extrabold break-words" style={{ color: "var(--color-text-primary)" }}>
              {idea.partner_team_name}
            </h3>
          </div>
          {idea.partner_team_archetype_label ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {idea.partner_team_archetype_label}
            </span>
          ) : null}
        </div>
        {idea.value_edge_band ? (
          <ToneBadge label={idea.value_edge_band} color={fairnessBandColor(idea.value_edge_band)} />
        ) : null}
      </div>
      {reason ? (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {reason}
        </p>
      ) : null}
      <ManagerTendenciesCard leagueId={leagueId} teamName={idea.partner_team_name} />

      {/* Width-fill fix (PR #1050, reconfirmed here): minmax(0,1fr) on both
          exchange columns, never max-content/auto-sized. */}
      <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 items-start">
        <ExchangeSide
          label="You send"
          dotColor="var(--color-danger)"
          assets={idea.package.send}
          total={{ text: sendTotal, color: "var(--color-text-secondary)" }}
        />
        <ExchangeSide
          label="You get"
          dotColor="var(--color-success)"
          assets={idea.package.receive}
          total={{ text: receiveTotal, color: "var(--color-text-secondary)" }}
        />
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Balance
        </span>
        <span className="text-xl font-black" style={{ color: deltaColor, fontVariantNumeric: "tabular-nums" }}>
          {deltaText}
        </span>
      </div>

      {isLowConfidence ? (
        <p className="text-xs" style={{ color: "var(--color-warning)" }}>
          {LOW_CONFIDENCE_USER_NOTE}
        </p>
      ) : null}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="inline-flex flex-1 items-center justify-center px-3 text-sm font-bold"
          style={{
            color: "var(--color-accent)",
            border: "1px solid var(--color-accent)",
            background: "color-mix(in srgb, var(--color-accent) 10%, transparent)",
            minHeight: "2.75rem",
          }}
          aria-expanded={expanded}
        >
          {expanded ? "Hide details" : "View details"}
        </button>
        <ShareTradeButton idea={idea} leagueId={leagueId} strategy={strategy} lens={lens} />
      </div>

      {expanded ? (
        <div className="flex flex-col gap-3 pt-2" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
          {moreReason ? (
            <div className="flex flex-col gap-1">
              <span className="text-xs uppercase font-bold" style={{ color: "var(--color-information)" }}>
                Why this works
              </span>
              <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {moreReason}
              </p>
            </div>
          ) : null}
          <LeanBarMeter sendScore={idea.send_score} receiveScore={idea.receive_score} />
          <BeginnerHelp term="ideaBalance" />
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
    </AccentCard>
  );
}
