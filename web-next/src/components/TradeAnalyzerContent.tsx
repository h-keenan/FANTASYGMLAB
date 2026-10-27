import { VerdictTrust } from "@/components/VerdictTrust";
import type { VerdictAssumptions } from "@/lib/verdictTrust";
import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { useEffect, useMemo, useRef, useState } from "react";

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
import { useShareImage } from "@/lib/useShareImage";
import { isPrivacyMode } from "@/lib/privacy";
import { shareCardCacheKey } from "@/lib/shareCard/cacheKey";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ExchangeSide, TradeAssetRow } from "@/components/TradeAssetExchange";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { PillRow } from "@/components/PillRow";
import { TradesTabBar } from "@/components/TradesTabBar";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { ManagerTendenciesCard } from "@/components/ManagerTendenciesCard";
import {
  confidenceLevel,
  formatTradeGain,
  LEVEL_SEGMENTS,
  levelColor,
  tradeShareRecord,
} from "@/lib/tradeHubPresentation";
import { tradePositionOptions } from "@/lib/idpPresentation";
import {
  ALL_POSITION_OPTIONS,
  ALL_TEAMS_ID,
  analyzeFailureMessage,
  pickToTradeAsset,
  playerToTradeAsset,
  tradeAnalyzerReasonMessage,
} from "@/lib/tradeAnalyzerPresentation";
import { ShareToCommunityToggle } from "@/components/ShareToCommunityToggle";
import { ValuesCredit } from "@/components/ValuesCredit";

/**
 * Trade Analyzer (Revision 15) — the manual "evaluate an offer you
 * received" builder: modules/trade_analyzer_ui.py's roster-browse assembly
 * + modules/trade_offer_analyzer.py's accept/decline/counter verdict,
 * reading/writing the exact same POST .../trade-analyzer mobile's
 * TradeAnalyzerScreen.tsx calls (no valuation logic duplicated here).
 * Distinct from Trade Hub's auto-generated ideas (TradeHubContent.tsx,
 * Revision 3): here the user picks the exact players/picks on each side.
 *
 * The builder mechanics (single active side + one shared search list below
 * it, add-on-tap) follow mobile's TradeAnalyzerScreen.tsx rather than
 * Streamlit's two-simultaneous-column layout — same roster-browse/search
 * contract the task called out, just the simpler of the two reference
 * shapes. The verdict card below it instead follows the CURRENT, already
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
 * activeSide + selectedTeamId and calls addPlayer's underlying state update
 * directly (not addPlayer() itself, since it reads the *current* activeSide
 * from a stale closure the same render tick activeSide is being set — see
 * the effect below). A player on the user's OWN roster sets activeSide to
 * "send" instead of "receive" (the only side that pool is drawn from) —
 * a deliberate, sensible deviation for that one edge case, not the literal
 * "always receive" reading. Fails open silently (plain Trade Analyzer view,
 * no crash) when the id is missing, stale, or isn't on any roster in this
 * league — there is no toast/error state for "couldn't find that player".
 *
 * Tap-depth audit 2026-10, proposal 1: after a quick-add the builder flips
 * to the OTHER (still empty) side and focuses the search box, so the next
 * tap picks the counter-asset. The owning team stays selected for when the
 * user comes back to "You receive". Used by Players' "Add to Trade" and the
 * Player Quick View / Player Profile "Add to Trade" action.
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

const MAX_SEARCH_RESULTS = 40;

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

function TradeSidePanel({
  label,
  dotColor,
  active,
  players,
  picks,
  onSelect,
  onRemovePlayer,
  onRemovePick,
}: {
  label: string;
  dotColor: string;
  active: boolean;
  players: RankedPlayer[];
  picks: DraftPickAsset[];
  onSelect: () => void;
  onRemovePlayer: (playerId: string) => void;
  onRemovePick: (pickId: string) => void;
}) {
  const hasAssets = players.length > 0 || picks.length > 0;
  return (
    <div
      className="glass-surface flex flex-col gap-2 p-3 min-w-0"
      style={active ? { borderColor: "var(--color-accent)" } : undefined}
    >
      <button type="button" onClick={onSelect} className="flex items-center gap-1.5 self-start">
        <span className="inline-block" style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor }} />
        <span
          className="uppercase text-xs font-bold"
          style={{
            letterSpacing: "var(--letter-spacing-badge)",
            color: active ? "var(--color-accent)" : "var(--color-text-muted)",
          }}
        >
          {label}
        </span>
      </button>
      {hasAssets ? (
        <div className="flex flex-col divide-y" style={{ borderColor: "var(--color-border)" }}>
          {players.map((player) => (
            <button
              key={`player-${player.player_id}`}
              type="button"
              onClick={() => onRemovePlayer(player.player_id)}
              className="w-full text-left"
              aria-label={`Remove ${player.name ?? "player"}`}
            >
              <TradeAssetRow asset={playerToTradeAsset(player)} disableQuickView />
            </button>
          ))}
          {picks.map((pick) => (
            <button
              key={`pick-${pick.pick_id}`}
              type="button"
              onClick={() => onRemovePick(pick.pick_id)}
              className="w-full text-left"
              aria-label={`Remove ${pick.label ?? "pick"}`}
            >
              <TradeAssetRow asset={pickToTradeAsset(pick)} />
            </button>
          ))}
        </div>
      ) : (
        <span className="text-xs italic" style={{ color: "var(--color-text-muted)" }}>
          Tap to add
        </span>
      )}
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
    `Balance: ${formatTradeGain(verdict.value_delta)}`;

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
  partnerTeamName,
  lens,
  cardTeams,
}: {
  verdict: TradeVerdict;
  sendAssets: TradeAsset[];
  receiveAssets: TradeAsset[];
  onBuildCounter: () => void;
  leagueId: string;
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
      <BeginnerHelp text={copy.verdictHelp(verdict.ui_verdict)} />

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
        <BeginnerHelp term="analyzerValueBalance" />
      </div>

      {verdict.rationale ? (
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase font-bold" style={{ color: "var(--color-information)" }}>
            {verdict.rationale_label || "Why this works"}
          </span>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {verdict.rationale}
          </p>
        </div>
      ) : null}

      {verdict.counter_guidance ? (
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase font-bold" style={{ color: "var(--color-accent)" }}>
            Next move
          </span>
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
        </div>
      ) : null}

      {alternatePackages.length > 0 ? (
        <div className="flex flex-col gap-2">
          <span
            className="text-xs uppercase font-bold"
            style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
          >
            Try this instead
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
              <TradeMatchup sendAssets={pkg.send_assets} receiveAssets={pkg.receive_assets} />
            </div>
          ))}
        </div>
      ) : null}

      <ConfidenceMeter
        label="Confidence"
        value={verdict.confidence}
        level={LEVEL_SEGMENTS[confidenceLvl]}
        color={levelColor(confidenceLvl)}
      />
      <BeginnerHelp term="analyzerConfidence" />

      {verdict.risk_summary ? (
        <div className="flex flex-col gap-1">
          <span className="text-xs uppercase font-bold" style={{ color: "var(--color-warning)" }}>
            Risk
          </span>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {verdict.risk_summary}
          </p>
        </div>
      ) : null}

      {verdict.roster_summary || verdict.strategy_summary ? (
        <details>
          <summary
            className="cursor-pointer text-xs uppercase font-bold"
            style={{ color: "var(--color-text-muted)" }}
          >
            More detail
          </summary>
          <div className="flex flex-col gap-2 pt-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
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

      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Reply to your partner directly — no in-app accept.
      </p>
    </AccentCard>
  );
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
  lens = "Dynasty",
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
  /** Valuation lens recorded with a shared trade. */
  lens?: string;
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
  const [activeSide, setActiveSide] = useState<"send" | "receive">("send");
  const [assetType, setAssetType] = useState<"players" | "picks">("players");
  const [positionFilter, setPositionFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [selectedTeamId, setSelectedTeamId] = useState(ALL_TEAMS_ID);
  const [analyzing, setAnalyzing] = useState(false);
  const [verdict, setVerdict] = useState<TradeVerdict | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  // Non-empty once the league's trade deadline has passed — the analyzer
  // stays open for offseason planning, this note just says so.
  const [planningNote, setPlanningNote] = useState("");
  const [assumptions, setAssumptions] = useState<VerdictAssumptions | null>(null);

  const selectedPlayerIds = useMemo(
    () => new Set([...sendPlayers, ...receivePlayers].map((p) => p.player_id)),
    [sendPlayers, receivePlayers],
  );
  const selectedPickIds = useMemo(
    () => new Set([...sendPicks, ...receivePicks].map((p) => p.pick_id)),
    [sendPicks, receivePicks],
  );
  const hasAnyAssets = sendPlayers.length > 0 || receivePlayers.length > 0 || sendPicks.length > 0 || receivePicks.length > 0;

  const positionOptions = useMemo(() => tradePositionOptions(ALL_POSITION_OPTIONS, rankings), [rankings]);

  const searchPool = useMemo(() => {
    if (activeSide === "send") return rankings.filter((p) => myRosterIds.has(p.player_id));
    if (selectedTeamId === ALL_TEAMS_ID) return rankings.filter((p) => !myRosterIds.has(p.player_id));
    const team = otherTeams.find((t) => t.rosterId === selectedTeamId);
    return team ? rankings.filter((p) => team.playerIds.has(p.player_id)) : [];
  }, [rankings, myRosterIds, otherTeams, selectedTeamId, activeSide]);

  const pickSearchPool = useMemo(() => {
    if (activeSide === "send") return picks.filter((p) => p.owner_roster_id === myRosterId);
    if (selectedTeamId === ALL_TEAMS_ID) return picks.filter((p) => p.owner_roster_id !== myRosterId);
    return picks.filter((p) => p.owner_roster_id === selectedTeamId);
  }, [picks, myRosterId, selectedTeamId, activeSide]);

  const playerResults = useMemo(() => {
    const query = search.trim().toLowerCase();
    return searchPool
      .filter((p) => !selectedPlayerIds.has(p.player_id))
      .filter((p) => !query || (p.name ?? "").toLowerCase().includes(query))
      .filter((p) => positionFilter === "ALL" || (p.position ?? "").toUpperCase() === positionFilter)
      .slice(0, MAX_SEARCH_RESULTS);
  }, [searchPool, selectedPlayerIds, search, positionFilter]);

  const pickResults = useMemo(() => {
    const query = search.trim().toLowerCase();
    return pickSearchPool
      .filter((p) => !selectedPickIds.has(p.pick_id))
      .filter((p) => !query || (p.label ?? "").toLowerCase().includes(query))
      .slice(0, MAX_SEARCH_RESULTS);
  }, [pickSearchPool, selectedPickIds, search]);

  function selectSide(side: "send" | "receive") {
    setActiveSide(side);
    setSearch("");
    setPositionFilter("ALL");
  }

  function addPlayer(player: RankedPlayer) {
    if (activeSide === "send") setSendPlayers((prev) => [...prev, player]);
    else setReceivePlayers((prev) => [...prev, player]);
    setVerdict(null);
    setAnalyzeError(null);
  }

  // Players' "Add to Trade" quick-add (Revision 20) — see this component's
  // own docstring. Applied at render time (React's documented "adjusting
  // state when a prop changes" pattern — see
  // react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  // — guarded by comparing against `appliedQuickAddPlayerId` so it runs once
  // per id), not inside a useEffect: a setState called synchronously inside
  // an effect body trips react-hooks/set-state-in-effect, the same rule
  // PlayerCompareContent.tsx's modelsLoadedFor comment already documents
  // working around elsewhere in this app. Deliberately does NOT call
  // addPlayer(): addPlayer reads `activeSide` from this render's closure,
  // and setActiveSide(...) a few lines below hasn't been committed yet this
  // same render, so addPlayer would still see the OLD side and file the
  // player on the wrong list.
  const [appliedQuickAddPlayerId, setAppliedQuickAddPlayerId] = useState<string | null>(null);
  const [quickAddFocusPending, setQuickAddFocusPending] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  // Focus is a DOM side effect, not state, so it runs after commit. The
  // pending flag is cleared by the input's own onFocus handler.
  useEffect(() => {
    if (quickAddFocusPending) searchInputRef.current?.focus({ preventScroll: true });
  }, [quickAddFocusPending]);
  if (quickAddPlayerId && quickAddPlayerId !== appliedQuickAddPlayerId) {
    setAppliedQuickAddPlayerId(quickAddPlayerId);
    const quickAddPlayer = rankings.find((p) => p.player_id === quickAddPlayerId);
    if (quickAddPlayer) {
      if (myRosterIds.has(quickAddPlayerId)) {
        // On the user's own roster: "receive" (the only side the search
        // pool ever draws from, see searchPool above) would be nonsensical.
        setActiveSide("receive");
        setQuickAddFocusPending(true);
        setSendPlayers((prev) =>
          prev.some((p) => p.player_id === quickAddPlayer.player_id) ? prev : [...prev, quickAddPlayer],
        );
      } else {
        const owner = otherTeams.find((team) => team.playerIds.has(quickAddPlayerId));
        if (owner) {
          setActiveSide("send");
          setQuickAddFocusPending(true);
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

  function addPick(pick: DraftPickAsset) {
    if (activeSide === "send") setSendPicks((prev) => [...prev, pick]);
    else setReceivePicks((prev) => [...prev, pick]);
    setVerdict(null);
    setAnalyzeError(null);
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
      setAssumptions(result.assumptions ?? null);
      trackUse("trade_analyzer", "evaluated", { leagueId, props: { result: result.verdict ? "verdict" : "no_verdict" } });
      if (result.verdict) {
        setVerdict(result.verdict);
      } else {
        setAnalyzeError(analyzeFailureMessage(result.reason));
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

  const sendAssets: TradeAsset[] = [...sendPlayers.map(playerToTradeAsset), ...sendPicks.map(pickToTradeAsset)];
  const receiveAssets: TradeAsset[] = [
    ...receivePlayers.map(playerToTradeAsset),
    ...receivePicks.map(pickToTradeAsset),
  ];

  const activeTeamLabel = otherTeams.find((t) => t.rosterId === selectedTeamId)?.label ?? "team";
  const searchPlaceholder =
    activeSide === "send"
      ? `Search your ${assetType === "picks" ? "picks" : "roster"}`
      : selectedTeamId === ALL_TEAMS_ID
        ? `Search ${assetType === "picks" ? "picks" : "players"} to receive`
        : `Search ${activeTeamLabel}'s ${assetType === "picks" ? "picks" : "roster"}`;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_analyzer" />
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Trade Analyzer
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Build an offer, get a verdict.
        </p>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 items-start">
        <TradeSidePanel
          label="You send"
          dotColor="var(--color-danger)"
          active={activeSide === "send"}
          players={sendPlayers}
          picks={sendPicks}
          onSelect={() => selectSide("send")}
          onRemovePlayer={(id) => removePlayer("send", id)}
          onRemovePick={(id) => removePick("send", id)}
        />
        <TradeSidePanel
          label="You receive"
          dotColor="var(--color-success)"
          active={activeSide === "receive"}
          players={receivePlayers}
          picks={receivePicks}
          onSelect={() => selectSide("receive")}
          onRemovePlayer={(id) => removePlayer("receive", id)}
          onRemovePick={(id) => removePick("receive", id)}
        />
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2 items-center">
          <PillRow
            options={[
              { label: "Players", value: "players" },
              { label: "Picks", value: "picks" },
            ]}
            active={assetType}
            onSelect={(value) => setAssetType(value === "picks" ? "picks" : "players")}
          />
          {assetType === "players" ? (
            <PillRow
              options={positionOptions.map((position) => ({ label: position, value: position }))}
              active={positionFilter}
              onSelect={setPositionFilter}
            />
          ) : null}
        </div>

        {activeSide === "receive" && otherTeams.length > 0 ? (
          <PillRow
            options={[
              { label: "All Teams", value: ALL_TEAMS_ID },
              ...otherTeams.map((team) => ({ label: team.label, value: team.rosterId })),
            ]}
            active={selectedTeamId}
            onSelect={setSelectedTeamId}
          />
        ) : null}

        {selectedTeamId !== ALL_TEAMS_ID ? (
          <ManagerTendenciesCard
            leagueId={leagueId}
            rosterId={selectedTeamId}
            teamName={teamProfiles[selectedTeamId]?.team_name ?? undefined}
          />
        ) : null}

        <input
          ref={searchInputRef}
          onFocus={() => setQuickAddFocusPending(false)}
          type="text"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={searchPlaceholder}
          className="glass-input w-full px-3 py-2 text-sm"
          style={{ color: "var(--color-text-primary)" }}
        />

        <div className="flex flex-col divide-y max-h-80 overflow-y-auto" style={{ borderColor: "var(--color-border)" }}>
          {assetType === "picks" ? (
            pickResults.length === 0 ? (
              <p className="text-sm py-2" style={{ color: "var(--color-text-muted)" }}>
                {search ? "No matching picks." : "Start typing to search, or browse the list above."}
              </p>
            ) : (
              pickResults.map((pick) => (
                <button key={pick.pick_id} type="button" className="w-full text-left" onClick={() => addPick(pick)}>
                  <TradeAssetRow asset={pickToTradeAsset(pick)} />
                </button>
              ))
            )
          ) : playerResults.length === 0 ? (
            <p className="text-sm py-2" style={{ color: "var(--color-text-muted)" }}>
              {search ? "No matching players." : "Start typing to search, or browse the list above."}
            </p>
          ) : (
            playerResults.map((player) => (
              <button
                key={player.player_id}
                type="button"
                className="w-full text-left"
                onClick={() => addPlayer(player)}
              >
                <TradeAssetRow asset={playerToTradeAsset(player)} disableQuickView />
              </button>
            ))
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {!hasAnyAssets ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Queue send and receive assets, then Analyze.
          </p>
        ) : null}
        <Button onClick={analyze} disabled={!hasAnyAssets} loading={analyzing}>
          {analyzing ? "Analyzing…" : "Analyze Trade"}
        </Button>
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

      {verdict ? (
        <>
        <VerdictCard
          verdict={verdict}
          sendAssets={sendAssets}
          receiveAssets={receiveAssets}
          onBuildCounter={applyCounterAction}
          leagueId={leagueId}
          partnerTeamName={selectedTeamId === ALL_TEAMS_ID ? "" : (teamProfiles[selectedTeamId]?.team_name ?? "")}
          lens={lens}
          cardTeams={{
            partnerAvatarUrl: selectedTeamId === ALL_TEAMS_ID ? null : (teamProfiles[selectedTeamId]?.avatar_url ?? null),
            myTeamName: teamProfiles[myRosterId]?.team_name ?? null,
            myAvatarUrl: teamProfiles[myRosterId]?.avatar_url ?? null,
          }}
        />
        <VerdictTrust
          assumptions={assumptions}
          context={{
            surface: "trade_analyzer",
            platform: "web",
            leagueId,
            lens,
            strategy: "retool",
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
      <ValuesCredit />
    </main>
  );
}
