"use client";

import { ConfirmInPlace } from "@/components/ui/ConfirmInPlace";
import { useEffect, useMemo, useRef, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { ErrorState } from "@/components/ErrorState";
import { PageTitle } from "@/components/PageTitle";
import { PitchShareButton } from "@/components/MultiTeamPitchButton";
import { TradePickerSheet } from "@/components/TradePickerSheet";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { PillRow } from "@/components/PillRow";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SkeletonBlock, SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { ExchangeSide, TradeAssetRow } from "@/components/TradeAssetExchange";
import { TradesTabBar } from "@/components/TradesTabBar";
import { ValuesCredit } from "@/components/ValuesCredit";
import { prefillToBuilder } from "@/lib/multiTeamIdeas";
import { api, type DraftPickAsset, type RankedPlayer, type TeamProfile, type TradeAsset } from "@/lib/api";
import { trackUse } from "@/lib/analytics";
import { isServerBusyError } from "@/lib/busyRetry";
import { mergeSearchMatches, useLeaguePlayerSearch } from "@/lib/leaguePlayerSearch";
import {
  MULTI_TEAM_MAX,
  MULTI_TEAM_MIN,
  addTeam,
  builderKey,
  analysisOrder,
  assetsLine,
  buildMatrix,
  buildShareModel,
  buildTransfers,
  builderIssue,
  flowReason,
  formatSigned,
  isMultiTradeOk,
  lineupEffectText,
  mostHurtBanner,
  multiTradeFailureLines,
  orderParticipants,
  removeAsset,
  removeTeam,
  toneSemantic,
  topReasons,
  upsertAsset,
  vetoTone,
  verdictChipLabel,
  analysisLayout,
  type BuilderAsset,
  type MultiAsset,
  type MultiTeamResult,
  type MultiTeamTradeResponse,
  type MultiTransfer,
  type SemanticTone,
} from "@/lib/multiTeamTrade";
import { pickToSheetItem, pickToTradeAsset, playerToSheetItem, playerToTradeAsset } from "@/lib/tradeAnalyzerPresentation";
import { selectedItems, type SheetItem } from "@/lib/tradeSheetPicker";
import { PopupShell } from "@/components/PopupShell";

/**
 * Multi-team (3 to 6 team) Trade Analyzer. Two separate surfaces:
 *
 * 1. ANALYSIS (private, honest): a team card per team with its verdict,
 *    value change, lineup effect, reasons and veto risk, headed by who is
 *    most hurt. 5 or 6 teams become a ranked list with tap to expand.
 * 2. SHARE (pitching the deal to the other managers): a persuasion framed
 *    picture, never a scoreboard (see lib/shareCard/multiTradeCard.tsx).
 *
 * Reads and writes POST .../trade-analyzer/multi; no valuation logic is
 * duplicated here. Presentation logic lives in lib/multiTeamTrade.ts, a
 * byte-identical twin of the mobile file.
 */

const TONE_VAR: Record<SemanticTone, string> = {
  success: "var(--color-success)",
  neutral: "var(--color-text-secondary)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
};

const BALANCE_TONE: Record<string, SemanticTone> = { balanced: "success", tilted: "warning", lopsided: "danger" };

/** Two teams (the standard Analyzer) or a 3 to 6 team trade. */
export function TradeModeToggle({ mode, onChange }: { mode: "two" | "multi"; onChange: (mode: "two" | "multi") => void }) {
  return (
    <PillRow
      ariaLabel="Trade type"
      options={[
        { label: "Two teams", value: "two" },
        { label: "Multi-team trade", value: "multi" },
      ]}
      active={mode}
      onSelect={(value) => onChange(value === "multi" ? "multi" : "two")}
    />
  );
}

function toTradeAsset(asset: MultiAsset): TradeAsset {
  return asset.type === "pick"
    ? { asset_type: "pick", label: asset.label, score: asset.score ?? null }
    : {
        asset_type: "player",
        player_id: asset.id,
        name: asset.label,
        position: asset.position,
        team: asset.team,
        age: asset.age ?? null,
        score: asset.score ?? null,
      };
}

export function failureMessage(error: unknown): string {
  if (isServerBusyError(error)) return "FantasyDesk is busy right now. Give it a moment and try again.";
  const rate = error as { status?: number; retryAfterSeconds?: number } | null;
  if (rate && rate.status === 429) {
    const wait = rate.retryAfterSeconds ? ` in ${rate.retryAfterSeconds} seconds` : " in a minute";
    return `You are analyzing a lot of trades at once. Try again${wait}.`;
  }
  return error instanceof Error ? error.message : "Could not analyze this trade.";
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------

function TeamResultBody({ team, vetoLocked }: { team: MultiTeamResult; vetoLocked: boolean }) {
  const reasons = topReasons(team, 3);
  const veto = team.veto_risk;
  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
        <ExchangeSide label="Sends" dotColor="var(--color-danger)" assets={team.sends.map(toTradeAsset)} />
        <ExchangeSide label="Receives" dotColor="var(--color-success)" assets={team.receives.map(toTradeAsset)} />
      </div>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {flowReason(team)}
      </p>
      {reasons.length ? (
        <ul className="flex flex-col gap-1 pl-4 list-disc text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {reasons.map((reason) => (
            <li key={`${reason.factor}-${reason.text}`}>{reason.text}</li>
          ))}
        </ul>
      ) : null}
      {veto ? (
        <div className="flex flex-col gap-1 items-start" data-testid="veto-risk">
          <ToneBadge label={`Veto risk: ${veto.label ?? veto.band ?? ""}`} color={TONE_VAR[vetoTone(veto.band)]} wrap />
          {veto.advice ? (
            <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {veto.advice}
            </span>
          ) : null}
        </div>
      ) : vetoLocked ? (
        <span className="text-xs" data-testid="veto-locked" style={{ color: "var(--color-text-muted)" }}>
          Veto risk is a Pro detail.
        </span>
      ) : null}
    </>
  );
}

function TeamStats({ team }: { team: MultiTeamResult }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm" style={{ fontVariantNumeric: "tabular-nums" }}>
      <span>
        <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Value{" "}
        </span>
        <strong>{formatSigned(team.market_delta)}</strong>
      </span>
      <span style={{ color: "var(--color-text-secondary)" }}>{lineupEffectText(team)}</span>
    </div>
  );
}

function TeamResultCard({ team, vetoLocked }: { team: MultiTeamResult; vetoLocked: boolean }) {
  const tone = TONE_VAR[toneSemantic(team.tone)];
  return (
    <AccentCard accent={tone} data-testid="team-result">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-black min-w-0 break-words">
          {team.team_name}
          {team.is_perspective ? (
            <span className="ml-2 text-xs font-bold uppercase" style={{ color: "var(--color-accent)" }}>
              You
            </span>
          ) : null}
        </h3>
        <ToneBadge label={verdictChipLabel(team)} color={tone} />
      </div>
      <TeamStats team={team} />
      <TeamResultBody team={team} vetoLocked={vetoLocked} />
    </AccentCard>
  );
}

function RankedRow({ team, rank, vetoLocked }: { team: MultiTeamResult; rank: number; vetoLocked: boolean }) {
  const [open, setOpen] = useState(false);
  const tone = TONE_VAR[toneSemantic(team.tone)];
  return (
    <AccentCard accent={tone} compact data-testid="team-result">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 text-left"
      >
        <span className="text-sm font-black w-5 shrink-0" style={{ color: "var(--color-text-muted)", fontVariantNumeric: "tabular-nums" }}>
          {rank}
        </span>
        <span className="flex-1 min-w-0 text-sm font-bold break-words">
          {team.team_name}
          {team.is_perspective ? " (you)" : ""}
        </span>
        <span className="text-sm font-black shrink-0" style={{ fontVariantNumeric: "tabular-nums" }}>
          {formatSigned(team.market_delta)}
        </span>
        <ToneBadge label={verdictChipLabel(team)} color={tone} />
      </button>
      {open ? (
        <div className="flex flex-col gap-3 pt-2">
          <TeamStats team={team} />
          <TeamResultBody team={team} vetoLocked={vetoLocked} />
        </div>
      ) : null}
    </AccentCard>
  );
}

function ResultsView({ response, leagueName, leagueId }: { response: MultiTeamTradeResponse; leagueName: string; leagueId: string }) {
  const ok = isMultiTradeOk(response);
  const banner = ok ? mostHurtBanner(response) : null;
  const ordered = useMemo(() => (ok ? analysisOrder(response) : []), [ok, response]);
  const model = useMemo(() => (ok ? buildShareModel(response) : null), [ok, response]);
  if (!ok || !banner || !model) return null;
  const ranked = analysisLayout(response.teams.length) === "ranked";
  const vetoLocked = Boolean(response.veto_locked);
  return (
    <section className="flex flex-col gap-3" aria-label="Trade analysis" data-testid="multi-team-results">
      <AccentCard accent={TONE_VAR[BALANCE_TONE[response.summary.balance.id] ?? "neutral"]} glow={false}>
        <p className="text-base font-black" data-testid="most-hurt-banner">
          {banner.headline}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <ToneBadge label={response.summary.balance.id} color={TONE_VAR[BALANCE_TONE[response.summary.balance.id] ?? "neutral"]} />
          <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {banner.balance}
          </span>
        </div>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {response.summary.headline}
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          This private read is for you. It does not use up a free evaluation.
        </p>
      </AccentCard>
      {vetoLocked ? (
        <PremiumUpsellCard
          bare
          kicker="Veto risk"
          upsell={response.veto_upsell ? { title: response.veto_upsell.title ?? "", body: response.veto_upsell.body ?? "" } : null}
          fallbackTitle="See which teams might cry foul"
          fallbackBody="Veto risk for every team is a Pro detail."
        />
      ) : null}
      {ranked
        ? ordered.map((team, index) => <RankedRow key={team.roster_id} team={team} rank={index + 1} vetoLocked={vetoLocked} />)
        : ordered.map((team) => <TeamResultCard key={team.roster_id} team={team} vetoLocked={vetoLocked} />)}
      <SharePitch response={response} leagueId={leagueId} leagueName={leagueName} />
    </section>
  );
}

/** The share surface: a pitch to the other managers, not the private read above. */
function SharePitch({ response, leagueId, leagueName }: { response: MultiTeamTradeResponse; leagueId: string; leagueName: string }) {
  const model = useMemo(() => buildShareModel(response), [response]);
  return (
    <div className="glass-surface flex flex-col gap-3 p-4" data-testid="multi-team-share">
      <h3 className="text-base font-black">Pitch it to the other managers</h3>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        The picture leads with what every team gets and the needs it fills. It still shows each team&apos;s real value change.
      </p>
      <ul className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {model.teams.map((team) => (
          <li key={team.rosterId}>
            <strong>{team.name}</strong> gets {assetsLine(team.gets)}
            {team.needs[0] ? `: ${team.needs[0]}` : ""}. Value change {team.valueChangeText}
            {team.getsBack ? `. ${team.getsBack}` : ""}.
          </li>
        ))}
      </ul>
      <PitchShareButton response={response} leagueId={leagueId} leagueName={leagueName} />
    </div>
  );
}

function ResultsSkeleton({ teams }: { teams: number }) {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" data-testid="multi-team-skeleton">
      <span className="sr-only" role="status">
        Grading the trade for every team
      </span>
      <SkeletonBlock height={72} radius="var(--radius-panel)" />
      {Array.from({ length: Math.min(4, Math.max(3, teams)) }, (_, i) => (
        <SkeletonCard key={i} lines={4} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Builder
// ---------------------------------------------------------------------------

interface PickerState {
  from: string;
  /** Preselected receiver (a matrix cell); empty opens the receiver sheet. */
  to: string;
}

export function MultiTeamTradeContent({
  leagueId,
  leagueName,
  myRosterId,
  rankings,
  picks,
  rosters,
  teamProfiles,
  lens,
  modeToggle,
  prefill,
}: {
  leagueId: string;
  leagueName: string;
  myRosterId: string;
  rankings: RankedPlayer[];
  picks: DraftPickAsset[];
  rosters: Array<Record<string, unknown>>;
  teamProfiles: Record<string, TeamProfile>;
  lens: string;
  /** The Two teams / Multi-team toggle, rendered under the title. */
  modeToggle: React.ReactNode;
  /** A trade to load into the builder and grade on open (a Trade Hub 3-team idea, `?multi=`). The
   * Analyzer regrades it: only ids travel, never a value or verdict. */
  prefill?: MultiTransfer[];
}) {
  const [participants, setParticipants] = useState<string[]>(() =>
    prefill?.length ? prefillToBuilder(prefill, myRosterId).participants : myRosterId ? [myRosterId] : [],
  );
  const [assets, setAssets] = useState<BuilderAsset[]>(() => (prefill?.length ? (prefillToBuilder(prefill, myRosterId).assets as BuilderAsset[]) : []));
  const [picker, setPicker] = useState<PickerState | null>(null);
  const [pending, setPending] = useState<BuilderAsset | null>(null);
  const [search, setSearch] = useState("");
  const { openPlayer } = usePlayerQuickView();
  const [analyzing, setAnalyzing] = useState(false);
  const [response, setResponse] = useState<MultiTeamTradeResponse | null>(null);
  const [failure, setFailure] = useState<string[] | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [addChoice, setAddChoice] = useState("");
  const resultsRef = useRef<HTMLDivElement | null>(null);

  const teamName = (rosterId: string) => teamProfiles[rosterId]?.team_name || teamProfiles[rosterId]?.owner_name || `Team ${rosterId}`;
  const rosterPlayers = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const roster of rosters) {
      const id = String((roster.roster_id as string | number | undefined) ?? "");
      const players = Array.isArray(roster.players) ? (roster.players as unknown[]) : [];
      if (id) map.set(id, new Set(players.map(String)));
    }
    return map;
  }, [rosters]);
  const leagueTeams = useMemo(
    () => [...rosterPlayers.keys()].sort((a, b) => teamName(a).localeCompare(teamName(b))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rosterPlayers, teamProfiles],
  );
  const addable = leagueTeams.filter((id) => !participants.includes(id));
  const ordered = orderParticipants(participants, myRosterId);

  const searchMatches = useLeaguePlayerSearch(leagueId, lens, picker ? search : "");
  const pool = useMemo(() => mergeSearchMatches(rankings, searchMatches), [rankings, searchMatches]);
  const playerById = useMemo(() => new Map(pool.map((p) => [p.player_id, p])), [pool]);
  const pickById = useMemo(() => new Map(picks.map((p) => [p.pick_id, p])), [picks]);

  // Items for the open sheet: the picking team's players and picks, plus anything it already sends that sits
  // outside the loaded pool, so applying never drops an asset.
  const sheetItems = useMemo<SheetItem<RankedPlayer | DraftPickAsset>[]>(() => {
    if (!picker) return [];
    const owned = rosterPlayers.get(picker.from) ?? new Set<string>();
    const sent = assets.filter((a) => a.fromRosterId === picker.from);
    const players = new Map(pool.filter((p) => owned.has(p.player_id)).map((p) => [p.player_id, p]));
    for (const a of sent) {
      const player = a.type === "player" ? playerById.get(a.id) : undefined;
      if (player) players.set(player.player_id, player);
    }
    const pickMap = new Map(picks.filter((p) => p.owner_roster_id === picker.from).map((p) => [p.pick_id, p]));
    for (const a of sent) {
      const pick = a.type === "pick" ? pickById.get(a.id) : undefined;
      if (pick) pickMap.set(pick.pick_id, pick);
    }
    return [...[...players.values()].map(playerToSheetItem), ...[...pickMap.values()].map(pickToSheetItem)];
  }, [picker, pool, rosterPlayers, picks, assets, playerById, pickById]);

  const issue = builderIssue(participants, assets);
  const transfersCount = assets.length;

  function invalidate() {
    setResponse(null);
    setFailure(null);
    setRequestError(null);
  }

  function addToTrade(asset: BuilderAsset) {
    setAssets((prev) => upsertAsset(prev, asset));
    invalidate();
  }

  /** The sheet's Apply: this team's sent assets become exactly the selection; kept ones keep their receiver. */
  function applySheet(keys: string[]) {
    if (!picker) return;
    const from = picker.from;
    const chosen = selectedItems(sheetItems, keys);
    const next: BuilderAsset[] = chosen.map((item) => {
      const type = item.kind;
      const existing = assets.find((a) => a.fromRosterId === from && a.type === type && a.id === item.id);
      return existing ?? { type, id: item.id, fromRosterId: from, toRosterId: picker.to };
    });
    setAssets((prev) => [...prev.filter((a) => a.fromRosterId !== from), ...next]);
    invalidate();
    setPicker(null);
    // Anything new without a receiver goes through the "Send to" sheet, one asset at a time.
    const unrouted = next.find((a) => !a.toRosterId);
    if (unrouted) setPending(unrouted);
  }

  function chooseDestination(toRosterId: string) {
    if (!pending) return;
    const routed = { ...pending, toRosterId };
    addToTrade(routed);
    const nextUnrouted = assets.find((a) => a.fromRosterId === pending.fromRosterId && !a.toRosterId && builderKey(a) !== builderKey(pending));
    setPending(nextUnrouted ?? null);
  }

  function addParticipant() {
    if (!addChoice) return;
    setParticipants((prev) => addTeam(prev, addChoice));
    setAddChoice("");
    invalidate();
  }

  function dropTeam(rosterId: string) {
    const next = removeTeam(participants, assets, rosterId);
    setParticipants(next.participants);
    setAssets(next.assets);
    if (picker?.from === rosterId) setPicker(null);
    invalidate();
  }

  async function analyze() {
    setFailure(null);
    setRequestError(null);
    setResponse(null);
    setAnalyzing(true);
    try {
      const result = await api.postMultiTeamTradeAnalyzer(leagueId, {
        transfers: buildTransfers(assets),
        perspectiveRosterId: myRosterId,
        lens,
      });
      trackUse("trade_analyzer", "evaluated", { leagueId, props: { item_kind: "multi_team", result: result.status === "ok" ? "verdict" : "no_verdict" } });
      if (isMultiTradeOk(result)) {
        setResponse(result);
        window.setTimeout(() => resultsRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }), 50);
      } else {
        setFailure(multiTradeFailureLines(result));
      }
    } catch (error) {
      setRequestError(failureMessage(error));
    } finally {
      setAnalyzing(false);
    }
  }

  const assetLabel = (a: BuilderAsset): TradeAsset | null => {
    if (a.type === "pick") {
      const pick = pickById.get(a.id);
      return pick ? pickToTradeAsset(pick) : { asset_type: "pick", label: a.id };
    }
    const player = playerById.get(a.id);
    return player ? playerToTradeAsset(player) : { asset_type: "player", player_id: a.id, name: `Player ${a.id}` };
  };

  const matrix = useMemo(() => buildMatrix(ordered, assets), [ordered, assets]);

  // A prefilled trade is graded once on open, the same request a tap on Analyze makes.
  const autoAnalyzed = useRef(false);
  useEffect(() => {
    if (!prefill?.length || autoAnalyzed.current) return;
    autoAnalyzed.current = true;
    void analyze();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="page-shell">
      <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_analyzer" />
      <header className="flex flex-col gap-2">
        <PageTitle page="Trade Analyzer" leagueName={leagueName} />
        {modeToggle}
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Build a trade between {MULTI_TEAM_MIN} to {MULTI_TEAM_MAX} teams. Add each team, then pick what every team sends and who receives it.
        </p>
      </header>

      <div className="flex flex-col gap-2" data-testid="multi-team-builder">
        {ordered.map((rosterId) => {
          const sends = assets.filter((a) => a.fromRosterId === rosterId);
          const isMe = rosterId === myRosterId;
          const open = picker?.from === rosterId;
          return (
            <div key={rosterId} className="glass-surface flex flex-col gap-2 p-3 min-w-0" style={open ? { borderColor: "var(--color-accent)" } : undefined} data-testid="team-panel">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-black min-w-0 break-words">
                  {teamName(rosterId)}
                  {isMe ? <span className="ml-2 text-xs font-bold uppercase" style={{ color: "var(--color-accent)" }}>You</span> : null}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  <Button size="sm" variant="secondary" onClick={() => { setPicker({ from: rosterId, to: "" }); setSearch(""); }}>
                    {sends.length ? "Edit assets" : "Add assets"}
                  </Button>
                  {!isMe ? (
                    // Dropping a team takes every asset routed to or from it, so it asks first
                    // (in place); an empty team is just removed.
                    assets.some((a) => a.fromRosterId === rosterId || a.toRosterId === rosterId) ? (
                      <ConfirmInPlace
                        variant="row"
                        mode="ask"
                        size="sm"
                        label="Remove"
                        ariaLabel={`Remove ${teamName(rosterId)}`}
                        prompt={`Remove ${teamName(rosterId)} and its assets?`}
                        confirmLabel="Remove"
                        buttonVariant="ghost"
                        onConfirm={() => dropTeam(rosterId)}
                      />
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => dropTeam(rosterId)} aria-label={`Remove ${teamName(rosterId)}`}>
                        Remove
                      </Button>
                    )
                  ) : null}
                </div>
              </div>
              {sends.length ? (
                <div className="flex flex-col divide-y" style={{ borderColor: "var(--color-border)" }}>
                  {sends.map((asset) => {
                    const display = assetLabel(asset);
                    return (
                      <div key={`${asset.type}:${asset.id}`} className="flex items-center gap-2">
                        <div className="flex-1 min-w-0">{display ? <TradeAssetRow asset={display} disableQuickView /> : null}</div>
                        <button
                          type="button"
                          className="tap-link text-xs font-bold shrink-0"
                          style={{ color: asset.toRosterId ? "var(--color-accent)" : "var(--color-warning)" }}
                          onClick={() => setPending(asset)}
                          aria-label={`Change who receives this asset`}
                        >
                          {asset.toRosterId ? `to ${teamName(asset.toRosterId)}` : "Choose team"}
                        </button>
                        <button type="button" className="tap-link text-xs shrink-0" onClick={() => { setAssets((prev) => removeAsset(prev, asset.type, asset.id)); invalidate(); }} aria-label="Remove asset">
                          Remove
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <span className="text-xs italic" style={{ color: "var(--color-text-muted)" }}>
                  Sends nothing yet
                </span>
              )}
            </div>
          );
        })}

        {participants.length < MULTI_TEAM_MAX ? (
          <div className="flex items-end gap-2">
            <div className="flex flex-col gap-1 flex-1 min-w-0">
              <label htmlFor="multi-add-team" className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
                Add a team
              </label>
              <select
                id="multi-add-team"
                value={addChoice}
                onChange={(event) => setAddChoice(event.target.value)}
                className="glass-input w-full px-3 py-2 text-sm"
                style={{ color: "var(--color-text-primary)" }}
              >
                <option value="">Choose a team</option>
                {addable.map((id) => (
                  <option key={id} value={id}>
                    {teamName(id)}
                  </option>
                ))}
              </select>
            </div>
            <Button variant="secondary" onClick={addParticipant} disabled={!addChoice}>
              Add team
            </Button>
          </div>
        ) : (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            A trade can include up to {MULTI_TEAM_MAX} teams.
          </p>
        )}
      </div>

      {participants.length >= MULTI_TEAM_MIN ? (
        <div className="hidden sm:flex flex-col gap-1" data-testid="trade-matrix">
          <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Who sends what to whom
          </span>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <caption className="sr-only">Rows are the sending team, columns the receiving team. Select a cell to add an asset for that pair.</caption>
              <thead>
                <tr>
                  <th scope="col" className="p-1 text-left" style={{ color: "var(--color-text-muted)" }}>
                    Sends / Receives
                  </th>
                  {ordered.map((to) => (
                    <th key={to} scope="col" className="p-1 text-left font-bold break-words">
                      {teamName(to)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ordered.map((from) => (
                  <tr key={from}>
                    <th scope="row" className="p-1 text-left font-bold break-words">
                      {teamName(from)}
                    </th>
                    {ordered.map((to) => {
                      const cell = matrix[from]?.[to] ?? [];
                      return (
                        <td key={to} className="p-1 align-top" style={{ border: "1px solid var(--color-border)" }}>
                          {from === to ? (
                            <span style={{ color: "var(--color-text-muted)" }}>-</span>
                          ) : (
                            <button
                              type="button"
                              className="w-full text-left"
                              onClick={() => { setPicker({ from, to }); setSearch(""); }}
                              aria-label={`Add an asset from ${teamName(from)} to ${teamName(to)}`}
                              style={{ color: cell.length ? "var(--color-text-primary)" : "var(--color-accent)" }}
                            >
                              {cell.length ? cell.map((a) => assetLabel(a)?.name || assetLabel(a)?.label || a.id).join(", ") : "+ Add"}
                            </button>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-2">
        <Button onClick={analyze} disabled={Boolean(issue)} loading={analyzing}>
          {analyzing ? "Analyzing…" : `Analyze ${participants.length}-team trade${transfersCount ? ` (${transfersCount} assets)` : ""}`}
        </Button>
        {issue ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {issue.message}
          </p>
        ) : null}
      </div>

      <div ref={resultsRef} className="flex flex-col gap-3">
        {analyzing ? <ResultsSkeleton teams={participants.length} /> : null}
        {requestError ? <ErrorState bare message={requestError} onRetry={analyze} /> : null}
        {failure ? (
          <div role="alert" className="glass-surface p-4 flex flex-col gap-1" data-testid="multi-team-failure">
            {failure.map((line) => (
              <p key={line} className="text-sm" style={{ color: "var(--color-danger)" }}>
                {line}
              </p>
            ))}
          </div>
        ) : null}
        {response ? <ResultsView response={response} leagueName={leagueName} leagueId={leagueId} /> : null}
      </div>

      {picker ? (
        <TradePickerSheet
          key={`${picker.from}>${picker.to}`}
          title={`${teamName(picker.from)} sends`}
          subtitle={picker.to ? `To ${teamName(picker.to)}` : "Choose who gets each asset next"}
          tone="danger"
          items={sheetItems}
          initialSelected={assets.filter((a) => a.fromRosterId === picker.from).map((a) => `${a.type}:${a.id}`)}
          onApply={applySheet}
          onClose={() => setPicker(null)}
          onSearch={setSearch}
          onInfo={(item) => openPlayer({ ...(item.ref as RankedPlayer), leagueId, leagueName, sourceLabel: "Trade Analyzer" })}
        />
      ) : null}

      {pending ? (
        <PopupShell title="Send to" onClose={() => setPending(null)} ariaLabel="Who receives this asset" portal={false}>
            <div className="flex flex-col gap-3 p-4">
              <h2 className="text-base font-black">Send to</h2>
              <div className="flex flex-col gap-2">
                {ordered
                  .filter((id) => id !== pending.fromRosterId)
                  .map((id) => (
                    <Button key={id} variant={pending.toRosterId === id ? "primary" : "secondary"} fullWidth onClick={() => chooseDestination(id)}>
                      {teamName(id)}
                    </Button>
                  ))}
              </div>
              <Button variant="ghost" onClick={() => setPending(null)}>
                Cancel
              </Button>
            </div>
        </PopupShell>
      ) : null}

      <ValuesCredit />
    </main>
  );
}

export type { MultiTeamResult };
