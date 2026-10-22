import { useMemo, useState } from "react";

import {
  api,
  type DraftPickAsset,
  type MyRosterResponse,
  type RankedPlayer,
  type TeamProfile,
  type TradeAsset,
  type TradeVerdict,
} from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ExchangeSide, TradeAssetRow } from "@/components/TradeAssetExchange";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { PillRow } from "@/components/PillRow";
import { TradesTabBar } from "@/components/TradesTabBar";
import { ValueRing } from "@/components/ValueRing";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { confidenceLevel, confidenceRingPercent, formatTradeGain, levelToRingTone } from "@/lib/tradeHubPresentation";
import {
  ALL_POSITION_OPTIONS,
  ALL_TEAMS_ID,
  analyzeFailureMessage,
  pickToTradeAsset,
  playerToTradeAsset,
  tradeAnalyzerReasonMessage,
} from "@/lib/tradeAnalyzerPresentation";
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

function VerdictCard({
  verdict,
  sendAssets,
  receiveAssets,
  onBuildCounter,
}: {
  verdict: TradeVerdict;
  sendAssets: TradeAsset[];
  receiveAssets: TradeAsset[];
  onBuildCounter: () => void;
}) {
  const toneColor = TONE_COLOR[verdict.tone];
  const deltaText = formatTradeGain(verdict.value_delta);
  const confidenceLvl = confidenceLevel(verdict.confidence);
  const confidencePercent = confidenceRingPercent(verdict.confidence);
  const sendTotal = sendAssets.reduce((sum, asset) => sum + (asset.score ?? 0), 0);
  const receiveTotal = receiveAssets.reduce((sum, asset) => sum + (asset.score ?? 0), 0);
  const alternatePackages = verdict.alternate_packages ?? [];
  const copy = useExperienceCopy();

  return (
    <section
      className="glass-surface flex flex-col gap-3 p-4"
      style={{ borderLeft: `var(--border-width-semantic) solid ${toneColor}` }}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span
          className="text-xs uppercase font-bold"
          style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          Reviewed package
        </span>
        <span className="text-lg font-black uppercase" style={{ color: toneColor }}>
          {verdict.ui_verdict}
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
            Why this works
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

      {/* Confidence then Risk — the same order (and the same ring primitive
          Trade Hub's confidence/realism rows use) as
          build_offer_result_card_html's own documented hierarchy. */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex flex-col items-center gap-1">
          <ValueRing
            percent={confidencePercent}
            tone={levelToRingTone(confidenceLvl)}
            display={`${confidencePercent}%`}
            ariaLabel={`Confidence: ${verdict.confidence}`}
            size="sm"
          />
          <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
            Confidence · {verdict.confidence}
          </span>
        </div>
      </div>
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

      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        There&apos;s no in-app accept, decline, or counter here — reply to your trade partner directly
        (Sleeper, group chat, etc.).
      </p>
    </section>
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

  const selectedPlayerIds = useMemo(
    () => new Set([...sendPlayers, ...receivePlayers].map((p) => p.player_id)),
    [sendPlayers, receivePlayers],
  );
  const selectedPickIds = useMemo(
    () => new Set([...sendPicks, ...receivePicks].map((p) => p.pick_id)),
    [sendPicks, receivePicks],
  );
  const hasAnyAssets = sendPlayers.length > 0 || receivePlayers.length > 0 || sendPicks.length > 0 || receivePicks.length > 0;

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
  if (quickAddPlayerId && quickAddPlayerId !== appliedQuickAddPlayerId) {
    setAppliedQuickAddPlayerId(quickAddPlayerId);
    const quickAddPlayer = rankings.find((p) => p.player_id === quickAddPlayerId);
    if (quickAddPlayer) {
      if (myRosterIds.has(quickAddPlayerId)) {
        // On the user's own roster: "receive" (the only side the search
        // pool ever draws from, see searchPool above) would be nonsensical.
        setActiveSide("send");
        setSendPlayers((prev) =>
          prev.some((p) => p.player_id === quickAddPlayer.player_id) ? prev : [...prev, quickAddPlayer],
        );
      } else {
        const owner = otherTeams.find((team) => team.playerIds.has(quickAddPlayerId));
        if (owner) {
          setActiveSide("receive");
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
          Evaluate an offer you received — build it exactly, get a real accept / decline / counter verdict.
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
              options={ALL_POSITION_OPTIONS.map((position) => ({ label: position, value: position }))}
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

        <input
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
        <button
          type="button"
          onClick={analyze}
          disabled={!hasAnyAssets || analyzing}
          className="self-start px-4 py-2 text-sm font-bold"
          style={{
            background: hasAnyAssets ? "var(--color-accent)" : "var(--color-surface-muted)",
            color: hasAnyAssets ? "#fff" : "var(--color-text-muted)",
          }}
        >
          {analyzing ? "Analyzing…" : "Analyze Trade"}
        </button>
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
        <VerdictCard
          verdict={verdict}
          sendAssets={sendAssets}
          receiveAssets={receiveAssets}
          onBuildCounter={applyCounterAction}
        />
      ) : hasAnyAssets ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          When both sides are ready, tap Analyze Trade for the verdict.
        </p>
      ) : null}
      <ValuesCredit />
    </main>
  );
}
