import { useState } from "react";
import { api, type TradeIdea } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { TeamAvatar } from "@/components/TeamAvatar";
import { TradeCategoryGlyph } from "@/components/TradeCategoryGlyph";
import { ValueRing } from "@/components/ValueRing";
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
  tradeIdeaShareText,
} from "@/lib/tradeHubPresentation";

/**
 * Shares a branded PNG (modules.share_card_renderer — QR code to the site,
 * FantasyDesk branding — the same mature pipeline the legacy Streamlit app
 * already uses for its player-quick-view share card) via the Files-capable
 * Web Share API when this idea/league/browser supports it. Falls back to
 * the original text-only navigator.share, then a clipboard copy, for any
 * idea/browser/OS that can't produce or share a file — never regresses the
 * prior text-only behavior.
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

  const shareTextOnly = async (text: string, title: string) => {
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({ text, title });
        return;
      } catch {
        // User cancelled the share sheet, or the platform rejected it —
        // either way, fall through to clipboard so the action never just
        // silently does nothing.
      }
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // No Share API and no clipboard permission — nothing more to do.
    }
  };

  const onShare = async () => {
    const text = tradeIdeaShareText(idea);
    const title = `Trade idea vs. ${idea.partner_team_name}`;

    const filesCapable =
      typeof navigator !== "undefined" &&
      typeof navigator.share === "function" &&
      typeof navigator.canShare === "function";

    if (filesCapable && leagueId && idea.recommendation_id) {
      setPreparingImage(true);
      try {
        const blob = await api.getTradeHubIdeaShareCardBlob(leagueId, idea.recommendation_id, strategy, lens);
        const file = new File([blob], `fantasydesk-trade-${idea.recommendation_id}.png`, {
          type: "image/png",
        });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], text, title });
          setPreparingImage(false);
          return;
        }
        // This browser/OS can share text but rejected this file — fall
        // through to the text-only path below rather than erroring.
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          // User cancelled the native share sheet — a deliberate no-op,
          // not a failure to fall back from.
          setPreparingImage(false);
          return;
        }
        // The PNG fetch failed (network, 404 on a stale recommendation_id,
        // etc.) or the platform otherwise rejected the file share — fall
        // through to the existing text-only path, same as always.
      }
      setPreparingImage(false);
    }

    await shareTextOnly(text, title);
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
}: {
  idea: TradeIdea;
  leagueId?: string;
  strategy?: string;
  lens?: string;
}) {
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
      className="glass-surface flex flex-col gap-3 p-4"
      style={{ borderLeft: `3px solid ${accent}` }}
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
