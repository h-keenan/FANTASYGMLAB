import { mergeSearchMatches, useLeaguePlayerSearch } from "@/lib/leaguePlayerSearch";
import type { OfferPrefill } from "@/lib/tradeOffer";
import { bridgeNotice, resolveBridgeTrade, type BridgeTrade } from "@/lib/tradeBridge";
import { VerdictTrust } from "@/components/VerdictTrust";
import type { VerdictAssumptions } from "@/lib/verdictTrust";
import type { RosterOverflow } from "@/lib/api";
import { RosterOverflowNote } from "@/components/SuggestedDrop";
import { AccentCard } from "@/components/AccentCard";
import { CompactModule } from "@/components/ui/CompactModule";
import { Button } from "@/components/Button";
import { LimitWall } from "@/components/LimitWall";
import { useAuth } from "@/context/AuthContext";
import { limitWallForReason, type LimitWallModel } from "@/lib/limitWall";
import { useMemo, useState, type ReactNode } from "react";
import { ToneBadge } from "@/components/ToneBadge";
import { TradeOddsEffect } from "@/components/TradeOddsEffect";

import {
  api,
  type DraftPickAsset,
  type MyRosterResponse,
  type RankedPlayer,
  type TeamProfile,
  type TradeAsset,
  type TradeVerdict,
} from "@/lib/api";
import { trackUse } from "@/lib/analytics";
import { isCompletedShare } from "@/lib/shareImage";
import { cautionDetail, cautionShareLine, verdictCautions } from "@/lib/tradeCautions";
import { useShareImage } from "@/lib/useShareImage";
import { isPrivacyMode } from "@/lib/privacy";
import { shareCardCacheKey } from "@/lib/shareCard/cacheKey";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { TradePickerSheet, TradeSideSummary } from "@/components/TradePickerSheet";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { Select } from "@/components/Input";
import { selectedItems, type SheetItem } from "@/lib/tradeSheetPicker";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { TradesTabBar } from "@/components/TradesTabBar";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { PostureChip } from "@/components/PostureChip";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { ManagerTendenciesCard } from "@/components/ManagerTendenciesCard";
import {
  confidenceLevel,
  formatTradeGain,
  LEVEL_SEGMENTS,
  levelColor,
  tradeShareRecord,
} from "@/lib/tradeHubPresentation";
import {
  ALL_TEAMS_ID,
  analyzeFailureMessage,
  pickToSheetItem,
  pickToTradeAsset,
  playerToSheetItem,
  playerToTradeAsset,
  tradeAnalyzerReasonMessage,
} from "@/lib/tradeAnalyzerPresentation";
import { dropRepeatedSentences, shortSummary } from "@/lib/verdictText";
import { ShareToCommunityToggle } from "@/components/ShareToCommunityToggle";
import { NextSteps } from "@/components/NextSteps";
import { ValuesCredit } from "@/components/ValuesCredit";
import { PageTitle } from "@/components/PageTitle";
import { MultiTeamTradeContent, TradeModeToggle } from "@/components/MultiTeamTradeContent";
import { isEspnLeagueId } from "@/lib/leaguePlatform";
import type { MultiTransfer } from "@/lib/multiTeamTrade";

/**
 * Trade Analyzer (Revision 15) — the manual "evaluate an offer you
 * received" builder: modules/trade_analyzer_ui.py's roster-browse assembly
 * + modules/trade_offer_analyzer.py's accept/decline/counter verdict,
 * reading/writing the exact same POST .../trade-analyzer mobile's
 * TradeAnalyzerScreen.tsx calls (no valuation logic duplicated here).
 * Distinct from Trade Hub's auto-generated ideas (TradeHubContent.tsx,
 * Revision 3): here the user picks the exact players/picks on each side.
 *
 * The builder: tap "You send" or "You receive" and the shared piece-picker sheet (TradePickerSheet, also used by
 * the multi-team builder and the Fantasy Sim trades builder) opens with that side's players and picks; Apply commits
 * the whole selection at once and the page keeps only a compact summary per side. Before 2026-11 a side tap just
 * flagged a hidden "active side" for a list far below the fold, which took several taps (see the repro in
 * scripts/trade_sheet_playwright). The  * verdict card below it follows the CURRENT, already
 * width-fill-fixed / zone-separated Streamlit result card
 * (build_offer_result_card_html): the give/receive matchup reuses
 * TradeHubContent's exact `minmax(0,1fr)` grid (never shrink-to-fit, the
 * bug fixed three times tonight) inside its own elevated panel, with a
 * single value-lean bar (LeanBarMeter, extracted for this page — see that
 * component's own docstring) and the Why → Action → Confidence → Risk
 * ordering `build_offer_result_card_html`'s own "Magna Carta §30" comment
 * documents.
 *
 * Revision 20 adds `quickAddPlayerId` — Players' "Add to Trade" row action
 * threads a tapped player's id through as ?playerId= (same gamePlanTileHref
 * convention Waivers/Trade Hub already read). On mount this resolves which
 * roster owns that player (myRosterIds / otherTeams, both already computed
 * below for the roster-browse search pool) and genuinely pre-populates the
 * builder — not just a highlight/scroll like Waivers' HighlightTarget: sets
 * selectedTeamId and the matching side's player list directly. A player on
 * the user's OWN roster goes to "You send" instead of "You receive" — a
 * deliberate, sensible deviation for that one edge case. Fails open silently (plain Trade Analyzer view,
 * no crash) when the id is missing, stale, or isn't on any roster in this
 * league — there is no toast/error state for "couldn't find that player".
 *
 * Used by Players' "Add to Trade" and the Player Quick View / Player
 * Profile "Add to Trade" action; the owning team is preselected as the
 * trade partner so the other side's sheet opens on the right roster.
 *
 * Revision 21 (coridian_, "add picks to all trade sections" audit): "Build
 * the counter" used to only ever appear/apply for a counter_action whose
 * asset_type was "player" — modules/trade_offer_analyzer.py's
 * build_counter_guidance has always been able to name a pick as the asset
 * to remove from your send side or ask for back (e.g. the weakest
 * outgoing asset in an overpay is often a cheap future pick, not a
 * player), the button just silently never rendered for that case. Fixed
 * on both ends: pick_asset_from_mapping now stamps a pick_id (the same
 * DraftPickAsset.pick_id format every picks list on this page already
 * keys on) onto every pick-type trade asset, and this component's
 * applyCounterAction branches on asset_type to mutate sendPicks/
 * receivePicks instead of sendPlayers/receivePlayers when it's set.
 */

interface OtherTeam {
  rosterId: string;
  label: string;
  playerIds: Set<string>;
}

const TONE_COLOR: Record<TradeVerdict["tone"], string> = {
  accept: "var(--color-success)",
  decline: "var(--color-danger)",
  counter: "var(--color-accent)",
  fair: "var(--color-text-secondary)",
};

/** Reusable 2-column (builder) / 3-column-with-FOR-divider (verdict review)
 * matchup grid — `minmax(0,1fr)` on every asset column, never max-content,
 * so a short side never lets the row shrink to its content width instead of
 * filling the half it owns (the dead-space-on-the-right bug Trade Hub's own
 * idea cards, GM Plan's teasers, and Streamlit's own give/get boxes all hit
 * and fixed separately tonight). */
function TradeMatchup({ sendAssets, receiveAssets }: { sendAssets: TradeAsset[]; receiveAssets: TradeAsset[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_1.5rem_minmax(0,1fr)] gap-3 items-start">
      <ExchangeSide label="You send" dotColor="var(--color-danger)" assets={sendAssets} />
      <div
        className="hidden sm:flex items-center justify-center text-xs font-bold uppercase self-stretch"
        style={{ color: "var(--color-accent)" }}
        aria-hidden="true"
      >
        FOR
      </div>
      <ExchangeSide label="You receive" dotColor="var(--color-success)" assets={receiveAssets} />
    </div>
  );
}

/** Team identity for the share card, all from data already on the page. */
export interface AnalyzerCardTeams {
  partnerAvatarUrl?: string | null;
  myTeamName?: string | null;
  myAvatarUrl?: string | null;
}

/** Shares the reviewed package as a branded PNG (falling back to text)
 * and records it for the "Did this trade happen?" prompt, same payload as
 * mobile's Analyzer share (TradeSharePreviewModal.recordShare). */
function ShareVerdictButton({
  leagueId,
  partnerTeamName,
  lens,
  verdict,
  sendAssets,
  receiveAssets,
  cardTeams,
}: {
  leagueId: string;
  partnerTeamName: string;
  lens: string;
  verdict: TradeVerdict;
  sendAssets: TradeAsset[];
  receiveAssets: TradeAsset[];
  cardTeams: AnalyzerCardTeams;
}) {
  const [copied, setCopied] = useState(false);
  const label = (assets: TradeAsset[]) => assets.map((a) => a.name).join(", ") || "nothing";

  const recordShare = () => {
    trackUse("trade_analyzer", "shared", { leagueId });
    void api
      .recordTradeShare(
        leagueId,
        tradeShareRecord({
          partnerTeamName,
          send: sendAssets,
          receive: receiveAssets,
          valueEdgeLabel: verdict.band,
          lens,
        }),
      )
      .catch(() => {});
  };

  const title = partnerTeamName ? `Trade vs. ${partnerTeamName}` : "Trade analysis";
  const text =
    `${title}: ${verdict.ui_verdict} (${verdict.band})\n` +
    `You send: ${label(sendAssets)}\nYou get: ${label(receiveAssets)}\n` +
    `Balance: ${formatTradeGain(verdict.value_delta)}` +
    (cautionShareLine(verdict) ? `\n${cautionShareLine(verdict)}` : "");

  // Branded PNG (QR + "For <partner>") drawn in the browser from the
  // analysis already on screen (no server call, no quota use). It is built
  // as soon as the result is on screen, so the Share tap calls
  // navigator.share({files}) inside the user gesture (iOS Safari).
  const params = { sendAssets, receiveAssets, verdict, lens, partnerName: partnerTeamName, ...cardTeams };
  const share = useShareImage({
    cacheKey: shareCardCacheKey({ params, privacy: isPrivacyMode() }),
    build: async () => {
      const { renderAnalyzerCardBlob } = await import("@/lib/shareCard/clientRender");
      return renderAnalyzerCardBlob(params);
    },
    filename: "fantasydesk-trade.png",
    text,
    title,
    itemKind: "trade_analyzer",
    leagueId,
    onOutcome: (outcome) => {
      if (isCompletedShare(outcome)) recordShare();
      if (outcome === "copied" || outcome === "copied-image" || outcome === "saved-image") {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    },
  });

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={share.onClick}
        disabled={share.busy}
        className="px-1.5 py-0.5 text-xs font-bold uppercase shrink-0"
        style={{ color: "var(--color-accent)", border: "1px solid var(--color-accent)" }}
      >
        {copied ? "Copied!" : share.label("Share")}
      </button>
      {share.status ? (
        <span role="status" className="text-xs font-normal normal-case" style={{ color: "var(--color-text-muted)" }}>
          {share.status}
        </span>
      ) : null}
    </span>
  );
}

function VerdictCard({
  verdict,
  sendAssets,
  receiveAssets,
  onBuildCounter,
  leagueId,
  leagueName,
  partnerTeamName,
  lens,
  cardTeams,
}: {
  verdict: TradeVerdict;
  sendAssets: TradeAsset[];
  receiveAssets: TradeAsset[];
  onBuildCounter: () => void;
  leagueId: string;
  leagueName: string;
  partnerTeamName: string;
  lens: string;
  cardTeams: AnalyzerCardTeams;
}) {
  const toneColor = TONE_COLOR[verdict.tone];
  const deltaText = formatTradeGain(verdict.value_delta);
  const confidenceLvl = confidenceLevel(verdict.confidence);
  const sendTotal = sendAssets.reduce((sum, asset) => sum + (asset.score ?? 0), 0);
  const receiveTotal = receiveAssets.reduce((sum, asset) => sum + (asset.score ?? 0), 0);
  const alternatePackages = verdict.alternate_packages ?? [];
  const copy = useExperienceCopy();
  // The lineup sentence used to print twice (lineup explanation + rationale).
  // Show a one-sentence summary by default; the rest sits behind "Read more".
  const lineupExplanation = verdict.lineup_model?.explanation ?? "";
  const summary = shortSummary(verdict.rationale || lineupExplanation);
  const rationaleRest = dropRepeatedSentences(verdict.rationale ?? "", [summary]);
  const lineupRest = dropRepeatedSentences(lineupExplanation, [summary, verdict.rationale ?? ""]);
  const hasMore = Boolean(
    rationaleRest || lineupRest || verdict.lineup_model || verdict.roster_summary || verdict.strategy_summary,
  );

  return (
    <AccentCard accent={toneColor} as="section">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span
          className="text-xs uppercase font-bold"
          style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          Reviewed package
        </span>
        <span className="flex items-center gap-2">
          <span className="text-lg font-black uppercase" style={{ color: toneColor }}>
            {verdict.ui_verdict}
          </span>
          <ShareVerdictButton
            leagueId={leagueId}
            partnerTeamName={partnerTeamName}
            lens={lens}
            verdict={verdict}
            sendAssets={sendAssets}
            receiveAssets={receiveAssets}
            cardTeams={cardTeams}
          />
        </span>
      </div>
      {verdict.band !== verdict.ui_verdict ? (
        <span className="text-xs font-bold self-start" style={{ color: toneColor }}>
          {verdict.band}
        </span>
      ) : null}
      {verdict.posture ? <PostureChip posture={verdict.posture} leagueId={leagueId} /> : null}
      {verdictCautions(verdict).map((caution) => (
        <div
          key={caution.code}
          role="note"
          data-testid="verdict-caution"
          className="flex flex-col gap-0.5 p-3"
          style={{ background: "var(--color-warning-soft)", borderLeft: "4px solid var(--color-warning)" }}
        >
          <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
            {caution.tag}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {cautionDetail(caution, verdict.band)}
          </span>
        </div>
      ))}
      <BeginnerHelp label="this verdict" text={copy.verdictHelp(verdict.ui_verdict)} />

      {/* Trade zone: the actual give/receive matchup, visually separated
          from the analysis content below it via an elevated panel — the
          same fix PR #1058 gave Streamlit's .toa-trade-zone after
          coridian_'s "everything is pretty much just on the gray or
          lighter gray background" flag. */}
      <div
        className="p-3"
        style={{ background: "var(--color-surface-raised)", border: "var(--border-width-default) solid var(--color-border)" }}
      >
        <TradeMatchup sendAssets={sendAssets} receiveAssets={receiveAssets} />
      </div>

      {(verdict.lineup_warnings ?? []).length > 0 ? (
        <ul className="flex flex-col gap-2" aria-label="Lineup warnings" data-testid="lineup-warnings">
          {(verdict.lineup_warnings ?? []).map((warning) => {
            const critical = warning.severity === "critical";
            return (
              <li
                key={`${warning.code}-${warning.position}`}
                role={critical ? "alert" : undefined}
                className="flex flex-col gap-0.5 p-3"
                style={{
                  background: "var(--color-warning-soft)",
                  borderLeft: `4px solid ${critical ? "var(--color-danger)" : "var(--color-warning)"}`,
                }}
              >
                <span className="text-sm font-bold" style={{ color: critical ? "var(--color-danger)" : "var(--color-text-primary)" }}>
                  {warning.headline}
                </span>
                <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                  {warning.detail}
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}

      <div className="flex flex-col gap-1.5">
        <div className="flex items-baseline gap-2">
          <span
            className="text-xs uppercase font-bold"
            style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
          >
            Value balance
          </span>
          <span className="text-2xl font-black" style={{ color: toneColor, fontVariantNumeric: "tabular-nums" }}>
            {deltaText}
          </span>
        </div>
        {/* Single value bar — never duplicated alongside a second meter for
            the same number (PR #1057 removed Streamlit's own duplicate). */}
        <LeanBarMeter sendScore={sendTotal} receiveScore={receiveTotal} />
        <BeginnerHelp label="value balance" term="analyzerValueBalance" />
      </div>

      <CompactModule
        id="analyzer.lineup"
        title="Lineup and odds"
        persist={false}
        parts={[
          verdict.lineup_model
            ? { key: "pts", text: `${formatLineupPoints(verdict.lineup_model.points.ros_delta)} lineup pts ROS`, strong: true, tone: verdict.posture_assessment?.lineup_costly ? "danger" : undefined }
            : { key: "pts", text: "Playoff and title odds effect", tone: "muted" },
          verdict.lineup_model ? { key: "wk", text: `${formatLineupPoints(verdict.lineup_model.points.this_week_delta)} this week` } : null,
        ]}
      >
      {verdict.lineup_model ? (
        <div className="flex flex-col gap-1" data-testid="lineup-model">
          <span
            className="text-xs uppercase font-bold"
            style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
          >
            Lineup impact
          </span>
          <p
            className="text-sm font-bold"
            style={{
              color: verdict.posture_assessment?.lineup_costly ? "var(--color-danger)" : "var(--color-text-primary)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {formatLineupPoints(verdict.lineup_model.points.ros_delta)} lineup pts over Weeks {verdict.lineup_model.weeks.first}-
            {verdict.lineup_model.weeks.last} ({formatLineupPoints(verdict.lineup_model.points.this_week_delta)} this week)
          </p>
        </div>
      ) : null}

      <TradeOddsEffect leagueId={leagueId} send={sendAssets} receive={receiveAssets} lens={lens} />
      </CompactModule>

      {summary ? (
        <InsightRow color="var(--color-information)" label={verdict.rationale_label || "Why this works"} icon={<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z" />}>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {summary}
          </p>
        </InsightRow>
      ) : null}

      <CompactModule
        id="analyzer.counter"
        title="Next move and alternatives"
        persist={false}
        defaultOpen={Boolean(verdict.counter_guidance)}
        parts={[
          verdict.counter_guidance ? { key: "g", text: shortSummary(verdict.counter_guidance) } : null,
          alternatePackages.length > 0
            ? { key: "alt", text: `${alternatePackages.length} alternative${alternatePackages.length === 1 ? "" : "s"}`, strong: true }
            : { key: "alt", text: verdict.counter_search?.status === "none" ? "No better package found" : "No alternatives", tone: "muted" },
        ]}
      >
      {verdict.counter_guidance ? (
        <InsightRow color="var(--color-accent)" label="Next move" icon={<path d="M5 12h14M13 6l6 6-6 6" />}>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {verdict.counter_guidance}
          </p>
          {verdict.counter_action ? (
            <button
              type="button"
              onClick={onBuildCounter}
              className="self-start text-sm font-bold"
              style={{ color: "var(--color-accent)" }}
            >
              Build the counter →
            </button>
          ) : null}
        </InsightRow>
      ) : null}

      {alternatePackages.length > 0 ? (
        <div className="flex flex-col gap-2">
          <span
            className="text-xs uppercase font-bold"
            style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
          >
            {alternatePackages.every((pkg) => pkg.clears_bar === false) ? "Closest counter" : "Try this instead"}
          </span>
          {alternatePackages.map((pkg, index) => (
            <div
              key={`${pkg.label}-${index}`}
              className="p-3"
              style={{ background: "var(--color-surface-raised)", border: "var(--border-width-default) solid var(--color-border)" }}
            >
              <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                <span className="text-sm font-bold">{pkg.label}</span>
                <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
                  {pkg.ui_verdict || pkg.band}
                </span>
              </div>
              {pkg.why ? (
                <p className="text-xs mb-2" style={{ color: "var(--color-text-secondary)" }}>
                  {pkg.why}
                </p>
              ) : null}
              <TradeMatchup sendAssets={pkg.send_assets} receiveAssets={pkg.receive_assets} />
              <p className="text-xs mt-2" style={{ color: "var(--color-text-muted)", fontVariantNumeric: "tabular-nums" }}>
                Value balance {formatTradeGain(pkg.value_delta)}
              </p>
            </div>
          ))}
        </div>
      ) : verdict.counter_search?.status === "none" ? (
        <p className="text-sm font-bold" data-testid="no-counter-found" style={{ color: "var(--color-text-secondary)" }}>
          {verdict.counter_search.message || "No better package found."}
        </p>
      ) : null}
      </CompactModule>

      <CompactModule
        id="analyzer.confidence"
        title="Confidence and risk"
        persist={false}
        parts={[
          { key: "c", text: `${verdict.confidence}${verdict.confidence_pct != null ? ` (${Math.round(verdict.confidence_pct)}%)` : ""} confidence`, strong: true },
          verdict.risk_summary ? { key: "r", text: shortSummary(verdict.risk_summary), tone: "warning" } : null,
        ]}
      >
      <ConfidenceMeter
        label="Confidence"
        value={verdict.confidence_pct != null ? `${verdict.confidence} (${Math.round(verdict.confidence_pct)}%)` : verdict.confidence}
        level={LEVEL_SEGMENTS[confidenceLvl]}
        color={levelColor(confidenceLvl)}
      />
      <BeginnerHelp label="confidence" term="analyzerConfidence" />

      {verdict.risk_summary ? (
        <InsightRow color="var(--color-warning)" label="Risk" icon={<path d="M12 4l9 16H3L12 4zM12 10v4M12 17h.01" />}>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {verdict.risk_summary}
          </p>
        </InsightRow>
      ) : null}
      </CompactModule>

      {hasMore ? (
        <details data-testid="verdict-read-more">
          <summary
            className="cursor-pointer text-xs uppercase font-bold"
            style={{ color: "var(--color-text-muted)" }}
          >
            Read more
          </summary>
          <div className="flex flex-col gap-2 pt-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {rationaleRest ? <p>{rationaleRest}</p> : null}
            {lineupRest ? <p>{lineupRest}</p> : null}
            {verdict.lineup_model ? (
              <p className="text-xs" style={{ color: "var(--color-text-muted)", fontVariantNumeric: "tabular-nums" }}>
                Trade score {formatTradeGain(verdict.lineup_model.trade_score)} = value balance plus lineup points under your posture.
              </p>
            ) : null}
            {verdict.roster_summary ? (
              <p>
                <strong>Roster impact:</strong> {verdict.roster_summary}
              </p>
            ) : null}
            {verdict.strategy_summary ? (
              <p>
                <strong>Strategy fit:</strong> {verdict.strategy_summary}
              </p>
            ) : null}
          </div>
        </details>
      ) : null}

      <ShareToCommunityToggle
        key={[...sendAssets, ...receiveAssets].map((a) => a.player_id || a.label || a.name).join("|") + verdict.band}
        verdict={verdict}
        sendAssets={sendAssets}
        receiveAssets={receiveAssets}
      />

      <NextSteps title="Want other options?" steps={["trade-finder", "trade-hub"]} leagueId={leagueId} leagueName={leagueName} />

      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Reply to your partner directly — no in-app accept.
      </p>
    </AccentCard>
  );
}

/** A verdict insight: tinted glyph, ToneBadge label, then the text. Replaces bare uppercase text labels. */
function InsightRow({
  color,
  label,
  icon,
  children,
}: {
  color: string;
  label: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <span
        className="inline-flex items-center justify-center shrink-0"
        style={{
          width: 32,
          height: 32,
          borderRadius: "var(--radius-pill)",
          background: `color-mix(in srgb, ${color} 15%, transparent)`,
          color,
        }}
        aria-hidden="true"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {icon}
        </svg>
      </span>
      <div className="flex flex-col gap-1 items-start min-w-0 flex-1">
        <ToneBadge label={label} color={color} wrap />
        {children}
      </div>
    </div>
  );
}

/** Signed lineup points with one decimal under 10, none above: "+4.2", "-92". */
function formatLineupPoints(points: number): string {
  const rounded = Math.abs(points) < 10 ? Math.round(points * 10) / 10 : Math.round(points);
  return `${rounded > 0 ? "+" : rounded < 0 ? "-" : ""}${Math.abs(rounded)}`;
}

export function TradeAnalyzerContent({
  leagueId,
  leagueName,
  myRoster,
  rankings,
  picks,
  rosters,
  teamProfiles,
  quickAddPlayerId,
  bridgeTrade,
  lens = "Dynasty",
  offerPrefill,
  multiPrefill,
}: {
  leagueId: string;
  leagueName: string;
  myRoster: MyRosterResponse;
  rankings: RankedPlayer[];
  picks: DraftPickAsset[];
  rosters: Array<Record<string, unknown>>;
  teamProfiles: Record<string, TeamProfile>;
  /** See this component's own docstring (Revision 20) — a Players row's
   * "Add to Trade" deep-link, ?playerId=. */
  quickAddPlayerId?: string;
  /** A trade entered on the public Trade Analyzer and carried through
   * sign-up (?a=&b=, see lib/tradeBridge.ts). Applied once on mount to the
   * builder, with a note for any player that does not fit this league. */
  bridgeTrade?: BridgeTrade | null;
  /** Valuation lens recorded with a shared trade. */
  lens?: string;
  /** A built offer ("Build an offer", ?send=&receive=&sendPicks=&receivePicks=)
   * to load into the builder so it can be tweaked, regraded and shared. */
  offerPrefill?: OfferPrefill | null;
  /** A 3-team trade (a Trade Hub idea, `?multi=`): opens the multi-team builder with it loaded and graded. */
  multiPrefill?: MultiTransfer[] | null;
}) {
  const reasonMessage = myRoster.reason ? tradeAnalyzerReasonMessage(myRoster.reason) : null;
  const myRosterId = String((myRoster.roster?.roster_id as string | number | undefined) ?? "");
  const myRosterIds = useMemo(() => {
    const players = Array.isArray(myRoster.roster?.players) ? (myRoster.roster!.players as unknown[]) : [];
    return new Set(players.map(String));
  }, [myRoster.roster]);

  const otherTeams = useMemo<OtherTeam[]>(() => {
    return rosters
      .map((roster) => {
        const rosterId = String((roster.roster_id as string | number | undefined) ?? "");
        const rosterPlayers = Array.isArray(roster.players) ? (roster.players as unknown[]) : [];
        const profile = teamProfiles[rosterId];
        const label =
          [profile?.team_name, profile?.owner_name].filter(Boolean).join(" · ") || `Team ${rosterId}`;
        return { rosterId, label, playerIds: new Set(rosterPlayers.map(String)) };
      })
      .filter((team) => team.rosterId && team.rosterId !== myRosterId)
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [rosters, teamProfiles, myRosterId]);

  const [sendPlayers, setSendPlayers] = useState<RankedPlayer[]>([]);
  const [receivePlayers, setReceivePlayers] = useState<RankedPlayer[]>([]);
  const [sendPicks, setSendPicks] = useState<DraftPickAsset[]>([]);
  const [receivePicks, setReceivePicks] = useState<DraftPickAsset[]>([]);
  // Which side's piece-picker sheet is open (tap a side to open it), and its search text for server-side matches.
  const [sheetSide, setSheetSide] = useState<"send" | "receive" | null>(null);
  const [sheetSearch, setSheetSearch] = useState("");
  const { openPlayer } = usePlayerQuickView();
  const [selectedTeamId, setSelectedTeamId] = useState(ALL_TEAMS_ID);
  const [analyzing, setAnalyzing] = useState(false);
  const [verdict, setVerdict] = useState<TradeVerdict | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [limitWall, setLimitWall] = useState<LimitWallModel | null>(null);
  const { isGuest } = useAuth();
  // Non-empty once the league's trade deadline has passed — the analyzer
  // stays open for offseason planning, this note just says so.
  const [planningNote, setPlanningNote] = useState("");
  const [roleNotes, setRoleNotes] = useState<string[]>([]);
  const [assumptions, setAssumptions] = useState<VerdictAssumptions | null>(null);
  const [rosterOverflow, setRosterOverflow] = useState<RosterOverflow | null>(null);
  // Two teams (this builder) or a 3 to 6 team trade (MultiTeamTradeContent).
  // Imported (ESPN, MFL, ...) leagues only get the two team Analyzer.
  const [tradeMode, setTradeMode] = useState<"two" | "multi">(multiPrefill?.length ? "multi" : "two");
  const multiTeamAvailable = !isEspnLeagueId(leagueId);

  const hasAnyAssets = sendPlayers.length > 0 || receivePlayers.length > 0 || sendPicks.length > 0 || receivePicks.length > 0;

  // The rankings prop is the top-300 window; a rostered player ranked below it
  // (rookie backup, etc.) must still be tradeable, so the sheet's search also asks the server.
  const searchMatches = useLeaguePlayerSearch(leagueId, lens, sheetSearch);
  const pool = useMemo(() => mergeSearchMatches(rankings, searchMatches), [rankings, searchMatches]);

  // Items for the open sheet: the side's own pool (your roster, or the partner's / everyone else's), plus whatever
  // that side already holds so applying never drops a prefilled asset that sits outside the pool.
  const sheetItems = useMemo<SheetItem<RankedPlayer | DraftPickAsset>[]>(() => {
    if (!sheetSide) return [];
    const partner = otherTeams.find((t) => t.rosterId === selectedTeamId);
    const players =
      sheetSide === "send"
        ? pool.filter((p) => myRosterIds.has(p.player_id))
        : selectedTeamId === ALL_TEAMS_ID
          ? pool.filter((p) => !myRosterIds.has(p.player_id))
          : partner
            ? pool.filter((p) => partner.playerIds.has(p.player_id))
            : [];
    const pickPool =
      sheetSide === "send"
        ? picks.filter((p) => p.owner_roster_id === myRosterId)
        : selectedTeamId === ALL_TEAMS_ID
          ? picks.filter((p) => p.owner_roster_id !== myRosterId)
          : picks.filter((p) => p.owner_roster_id === selectedTeamId);
    const held = sheetSide === "send" ? { players: sendPlayers, picks: sendPicks } : { players: receivePlayers, picks: receivePicks };
    const playerItems = [...new Map([...players, ...held.players].map((p) => [p.player_id, p])).values()].map(playerToSheetItem);
    const pickItems = [...new Map([...pickPool, ...held.picks].map((p) => [p.pick_id, p])).values()].map(pickToSheetItem);
    return [...playerItems, ...pickItems];
  }, [sheetSide, pool, picks, myRosterIds, myRosterId, otherTeams, selectedTeamId, sendPlayers, sendPicks, receivePlayers, receivePicks]);

  function openSheet(side: "send" | "receive") {
    setSheetSearch("");
    setSheetSide(side);
  }

  /** The sheet's Apply: replace this side's players and picks with the selection in one step. */
  function applySheet(keys: string[]) {
    if (!sheetSide) return;
    const chosen = selectedItems(sheetItems, keys);
    const players = chosen.filter((i) => i.kind === "player").map((i) => i.ref as RankedPlayer);
    const pickList = chosen.filter((i) => i.kind === "pick").map((i) => i.ref as DraftPickAsset);
    if (sheetSide === "send") {
      setSendPlayers(players);
      setSendPicks(pickList);
    } else {
      setReceivePlayers(players);
      setReceivePicks(pickList);
    }
    setVerdict(null);
    setAnalyzeError(null);
    setSheetSide(null);
  }

  function removeFromSide(side: "send" | "receive", key: string) {
    const [kind, ...rest] = key.split(":");
    const id = rest.join(":");
    if (kind === "pick") removePick(side, id);
    else removePlayer(side, id);
  }

  // Players' "Add to Trade" quick-add (Revision 20) — see this component's
  // own docstring. Applied at render time (React's documented "adjusting
  // state when a prop changes" pattern — see
  // react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  // — guarded by comparing against `appliedQuickAddPlayerId` so it runs once
  // per id), not inside a useEffect: a setState called synchronously inside
  // an effect body trips react-hooks/set-state-in-effect, the same rule
  // PlayerCompareContent.tsx's modelsLoadedFor comment already documents
  // working around elsewhere in this app.
  const [appliedQuickAddPlayerId, setAppliedQuickAddPlayerId] = useState<string | null>(null);
  if (quickAddPlayerId && quickAddPlayerId !== appliedQuickAddPlayerId) {
    setAppliedQuickAddPlayerId(quickAddPlayerId);
    const quickAddPlayer = rankings.find((p) => p.player_id === quickAddPlayerId);
    if (quickAddPlayer) {
      if (myRosterIds.has(quickAddPlayerId)) {
        // On the user's own roster: "receive" would be nonsensical.
        setSendPlayers((prev) =>
          prev.some((p) => p.player_id === quickAddPlayer.player_id) ? prev : [...prev, quickAddPlayer],
        );
      } else {
        const owner = otherTeams.find((team) => team.playerIds.has(quickAddPlayerId));
        if (owner) {
          setSelectedTeamId(owner.rosterId);
          setReceivePlayers((prev) =>
            prev.some((p) => p.player_id === quickAddPlayer.player_id) ? prev : [...prev, quickAddPlayer],
          );
        }
        // else: not on any roster in this league — fail open, no crash.
      }
    }
    // else: missing/stale id, or not in this league's pool — fail open.
  }

  // Public Trade Analyzer bridge: same render-time "apply once" pattern as the
  // quick-add above (keyed on the trade's ids so it runs once per trade).
  const bridgeKey = bridgeTrade ? `${bridgeTrade.a.join(",")}|${bridgeTrade.b.join(",")}` : null;
  const [appliedBridgeKey, setAppliedBridgeKey] = useState<string | null>(null);
  const [bridgeMessage, setBridgeMessage] = useState("");
  if (bridgeTrade && bridgeKey !== appliedBridgeKey) {
    setAppliedBridgeKey(bridgeKey);
    const resolution = resolveBridgeTrade({ trade: bridgeTrade, rankings, myRosterIds, otherTeams });
    setSendPlayers(resolution.send);
    setReceivePlayers(resolution.receive);
    if (resolution.partnerRosterId) setSelectedTeamId(resolution.partnerRosterId);
    setBridgeMessage(bridgeNotice(resolution));
  }

  // "Build an offer" hand-off: same render-time "apply once" pattern as the
  // bridge above. Ids that are not in this league's pool are skipped, never
  // invented; the verdict is always the Analyzer's own regrade.
  const offerKey = offerPrefill
    ? [offerPrefill.send, offerPrefill.receive, offerPrefill.sendPicks, offerPrefill.receivePicks].map((l) => l.join(",")).join("|")
    : null;
  const [appliedOfferKey, setAppliedOfferKey] = useState<string | null>(null);
  if (offerPrefill && offerKey !== appliedOfferKey) {
    setAppliedOfferKey(offerKey);
    const byId = new Map(rankings.map((p) => [p.player_id, p]));
    const pickById = new Map(picks.map((p) => [p.pick_id, p]));
    const sendList = offerPrefill.send.map((id) => byId.get(id)).filter((p): p is RankedPlayer => Boolean(p));
    const receiveList = offerPrefill.receive.map((id) => byId.get(id)).filter((p): p is RankedPlayer => Boolean(p));
    setSendPlayers(sendList);
    setReceivePlayers(receiveList);
    setSendPicks(offerPrefill.sendPicks.map((id) => pickById.get(id)).filter((p): p is DraftPickAsset => Boolean(p)));
    setReceivePicks(offerPrefill.receivePicks.map((id) => pickById.get(id)).filter((p): p is DraftPickAsset => Boolean(p)));
    const owner = otherTeams.find((team) => receiveList.some((p) => team.playerIds.has(p.player_id)));
    if (owner) setSelectedTeamId(owner.rosterId);
  }

  function removePlayer(side: "send" | "receive", playerId: string) {
    if (side === "send") setSendPlayers((prev) => prev.filter((p) => p.player_id !== playerId));
    else setReceivePlayers((prev) => prev.filter((p) => p.player_id !== playerId));
    setVerdict(null);
  }

  function removePick(side: "send" | "receive", pickId: string) {
    if (side === "send") setSendPicks((prev) => prev.filter((p) => p.pick_id !== pickId));
    else setReceivePicks((prev) => prev.filter((p) => p.pick_id !== pickId));
    setVerdict(null);
  }

  async function analyze() {
    setAnalyzeError(null);
    setLimitWall(null);
    setAnalyzing(true);
    try {
      const result = await api.postTradeAnalyzer(leagueId, {
        sendPlayerIds: sendPlayers.map((p) => p.player_id),
        receivePlayerIds: receivePlayers.map((p) => p.player_id),
        sendPickIds: sendPicks.map((p) => p.pick_id),
        receivePickIds: receivePicks.map((p) => p.pick_id),
        partnerRosterId: selectedTeamId === ALL_TEAMS_ID ? "" : selectedTeamId,
      });
      setPlanningNote(result.planning_note ?? "");
      setRoleNotes(result.role_notes ?? []);
      setAssumptions(result.assumptions ?? null);
      setRosterOverflow(result.roster_overflow ?? null);
      trackUse("trade_analyzer", "evaluated", { leagueId, props: { result: result.verdict ? "verdict" : "no_verdict" } });
      if (result.verdict) {
        setVerdict(result.verdict);
      } else {
        const wall = limitWallForReason(result.reason, { info: result.limit, isGuest });
        if (wall) setLimitWall(wall);
        else setAnalyzeError(analyzeFailureMessage(result.reason));
      }
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : "Could not analyze this trade.");
    } finally {
      setAnalyzing(false);
    }
  }

  function applyCounterAction() {
    const action = verdict?.counter_action;
    if (!action || !action.player_id) return;
    if (action.asset_type === "pick") {
      // Picks round-trip through `player_id` too (trade_analyzer_assembly.
      // pick_asset_from_mapping's `pick_id`, the same DraftPickAsset.pick_id
      // every other picks list on this page already keys on) — see this
      // function's player branch below for the original player-only version.
      if (action.action === "remove_from_send") {
        setSendPicks((prev) => prev.filter((p) => p.pick_id !== action.player_id));
      } else if (action.action === "add_to_receive") {
        const pick = picks.find((p) => p.pick_id === action.player_id);
        if (!pick) return;
        setReceivePicks((prev) => (prev.some((p) => p.pick_id === pick.pick_id) ? prev : [...prev, pick]));
      }
    } else if (action.action === "remove_from_send") {
      setSendPlayers((prev) => prev.filter((p) => p.player_id !== action.player_id));
    } else if (action.action === "add_to_receive") {
      const player = rankings.find((p) => p.player_id === action.player_id);
      if (!player) return;
      setReceivePlayers((prev) => (prev.some((p) => p.player_id === player.player_id) ? prev : [...prev, player]));
    }
    setVerdict(null);
    setAnalyzeError(null);
  }

  if (reasonMessage) {
    return (
      <main className="flex-1 flex flex-col gap-4 items-center justify-center px-4">
        <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_analyzer" />
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {reasonMessage}
        </p>
      </main>
    );
  }

  if (tradeMode === "multi" && multiTeamAvailable) {
    return (
      <MultiTeamTradeContent
        leagueId={leagueId}
        leagueName={leagueName}
        myRosterId={myRosterId}
        rankings={rankings}
        picks={picks}
        rosters={rosters}
        teamProfiles={teamProfiles}
        lens={lens}
        modeToggle={<TradeModeToggle mode={tradeMode} onChange={setTradeMode} />}
        prefill={multiPrefill ?? undefined}
      />
    );
  }

  const sendAssets: TradeAsset[] = [...sendPlayers.map(playerToTradeAsset), ...sendPicks.map(pickToTradeAsset)];
  const receiveAssets: TradeAsset[] = [
    ...receivePlayers.map(playerToTradeAsset),
    ...receivePicks.map(pickToTradeAsset),
  ];

  const canAnalyze = hasAnyAssets;
  const analyzeLabel = canAnalyze
    ? `Analyze Trade (${sendAssets.length} for ${receiveAssets.length})`
    : "Analyze Trade";

  const activeTeamLabel = otherTeams.find((t) => t.rosterId === selectedTeamId)?.label ?? "team";

  return (
    <main className="page-shell">
      <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_analyzer" />
      <header className="flex flex-col gap-1">
        <PageTitle page="Trade Analyzer" leagueName={leagueName} />
        {multiTeamAvailable ? <TradeModeToggle mode={tradeMode} onChange={setTradeMode} /> : null}
      </header>

      {bridgeMessage ? (
        <p className="m-0 text-sm" role="status" data-testid="bridge-notice" style={{ color: "var(--color-text-secondary)" }}>
          {bridgeMessage}
        </p>
      ) : null}

      {otherTeams.length > 0 ? (
        <label className="flex flex-col gap-1">
          <span className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Trading with
          </span>
          <Select
            aria-label="Trading with"
            value={selectedTeamId}
            onChange={(event) => setSelectedTeamId(event.target.value)}
          >
            <option value={ALL_TEAMS_ID}>Any team</option>
            {otherTeams.map((team) => (
              <option key={team.rosterId} value={team.rosterId}>
                {team.label}
              </option>
            ))}
          </Select>
        </label>
      ) : null}

      <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 items-start">
        <TradeSideSummary
          testId="trade-side-send"
          label="You send"
          tone="danger"
          items={[...sendPlayers.map(playerToSheetItem), ...sendPicks.map(pickToSheetItem)]}
          onOpen={() => openSheet("send")}
          onRemove={(key) => removeFromSide("send", key)}
          hint="Add from your roster"
        />
        <TradeSideSummary
          testId="trade-side-receive"
          label="You receive"
          tone="success"
          items={[...receivePlayers.map(playerToSheetItem), ...receivePicks.map(pickToSheetItem)]}
          onOpen={() => openSheet("receive")}
          onRemove={(key) => removeFromSide("receive", key)}
          hint={selectedTeamId === ALL_TEAMS_ID ? "Add from any team" : `Add from ${activeTeamLabel}`}
        />
      </div>

      {selectedTeamId !== ALL_TEAMS_ID ? (
        <ManagerTendenciesCard
          leagueId={leagueId}
          rosterId={selectedTeamId}
          teamName={teamProfiles[selectedTeamId]?.team_name ?? undefined}
        />
      ) : null}

      <div className="flex flex-col gap-2">
        <Button onClick={analyze} disabled={!canAnalyze} loading={analyzing}>
          {analyzing ? "Analyzing…" : analyzeLabel}
        </Button>
        {!canAnalyze ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Add players or picks to analyze.
          </p>
        ) : null}
        {limitWall ? <LimitWall wall={limitWall} feature="trade_analyzer_weekly_limit" /> : null}
        {analyzeError ? (
          <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>
            {analyzeError}
          </p>
        ) : null}
      </div>

      {planningNote ? (
        <p className="glass-surface text-sm p-4" style={{ color: "var(--color-text-secondary)" }}>
          {planningNote}
        </p>
      ) : null}

      {roleNotes.length ? (
        <div className="glass-surface p-4 flex flex-col gap-1" data-testid="trade-role-notes">
          <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Role changes (Pro)
          </span>
          {roleNotes.map((line) => (
            <span key={line} className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {line}
            </span>
          ))}
        </div>
      ) : null}

      {verdict ? (
        <>
        <VerdictCard
          verdict={verdict}
          sendAssets={sendAssets}
          receiveAssets={receiveAssets}
          onBuildCounter={applyCounterAction}
          leagueId={leagueId}
          leagueName={leagueName}
          partnerTeamName={selectedTeamId === ALL_TEAMS_ID ? "" : (teamProfiles[selectedTeamId]?.team_name ?? "")}
          lens={lens}
          cardTeams={{
            partnerAvatarUrl: selectedTeamId === ALL_TEAMS_ID ? null : (teamProfiles[selectedTeamId]?.avatar_url ?? null),
            myTeamName: teamProfiles[myRosterId]?.team_name ?? null,
            myAvatarUrl: teamProfiles[myRosterId]?.avatar_url ?? null,
          }}
        />
        {rosterOverflow ? <RosterOverflowNote overflow={rosterOverflow} /> : null}
        <VerdictTrust
          assumptions={assumptions}
          context={{
            surface: "trade_analyzer",
            platform: "web",
            leagueId,
            lens,
            strategy: verdict.posture?.key ?? "retool",
            sendIds: [...sendPlayers.map((p) => p.player_id), ...sendPicks.map((p) => p.pick_id)],
            receiveIds: [...receivePlayers.map((p) => p.player_id), ...receivePicks.map((p) => p.pick_id)],
            verdictLabel: verdict.ui_verdict,
            confidence: verdict.confidence,
            valueDelta: verdict.value_delta,
            assumptionsLine: assumptions?.line ?? "",
          }}
        />
        </>
      ) : hasAnyAssets ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          When both sides are ready, tap Analyze Trade for the verdict.
        </p>
      ) : null}
      {sheetSide ? (
        <TradePickerSheet
          key={sheetSide}
          title={sheetSide === "send" ? "You send" : "You receive"}
          subtitle={sheetSide === "send" ? "From your roster" : selectedTeamId === ALL_TEAMS_ID ? "From any team" : `From ${activeTeamLabel}`}
          tone={sheetSide === "send" ? "danger" : "success"}
          items={sheetItems}
          initialSelected={[
            ...(sheetSide === "send" ? sendPlayers : receivePlayers).map((p) => `player:${p.player_id}`),
            ...(sheetSide === "send" ? sendPicks : receivePicks).map((p) => `pick:${p.pick_id}`),
          ]}
          onApply={applySheet}
          onClose={() => setSheetSide(null)}
          onSearch={setSheetSearch}
          onInfo={(item) => {
            const player = item.ref as RankedPlayer;
            openPlayer({ ...player, leagueId, leagueName, sourceLabel: "Trade Analyzer" });
          }}
        />
      ) : null}

      <ValuesCredit />
    </main>
  );
}
