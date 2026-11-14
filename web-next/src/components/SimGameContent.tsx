"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState, useSyncExternalStore } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button, ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Input, Select } from "@/components/Input";
import { PageTitle } from "@/components/PageTitle";
import { PillRow } from "@/components/PillRow";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SectionHeading } from "@/components/SectionHeading";
import { SimDraftRecapView, SimGameDraft } from "@/components/SimGameDraft";
import { SimLeagueTab } from "@/components/SimGameLeague";
import { SimGameOffseason } from "@/components/SimGameOffseason";
import { SimHomeTab } from "@/components/SimGameHome";
import { SimPlayerSheet } from "@/components/SimGamePlayers";
import { SimActionBar } from "@/components/SimActionBar";
import { SimGameHeader, SimStatusChips } from "@/components/SimGameHeader";
import { SimGameOrb } from "@/components/SimGameOrb";
import { Sheet } from "@/components/ui/Sheet";
import { SimNotificationBell, useSimNotifications } from "@/components/SimNotificationBell";
import { SimOffseasonBar } from "@/components/SimOffseasonBar";
import { ConfirmInPlace } from "@/components/ui/ConfirmInPlace";
import { SimGlyph } from "@/components/SimGlyph";
import { simHubRow } from "@/lib/simHub";
import { simMenuHero, simRulesParts } from "@/lib/simSummaries";
import { Hero } from "@/components/ui/ModuleTemplates";
import { CompactModule } from "@/components/ui/CompactModule";
import { SimNotice, SimOpenPlayerContext, SimPreviewBanner, SimProgressBar, SimTeamLink, SimTeamOpenContext, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { SimBlockToggle } from "@/components/SimTradeBlock";
import { SimTeamSheet } from "@/components/SimGameTeamSheet";
import { SimToResultView, SimToSheet, type SimToRequest } from "@/components/SimToControl";
import { SimFinalView } from "@/components/SimGameRecap";
import { SimWeekRecapStory } from "@/components/SimRecapStory";
import { SimPlayersTab, SimTeamTab } from "@/components/SimGameTeam";
import { SimTradesTab } from "@/components/SimGameTrades";
import { SkeletonCard } from "@/components/Skeleton";
import { DifficultyTiles, SetupCard, SetupField, SetupNote, SetupStickyBar, SetupSummaryCard, SetupToggleGroup, SetupToggleRow } from "@/components/SimSetupParts";
import { MotionIn } from "@/components/Motion";
import { SIM_DIFFICULTY_FOOTNOTE, SIM_SETUP_TABS, simSetupCardSummaries, simSetupChips, simSetupHeadline, type SimSetupTab } from "@/lib/simSetupView";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { ToneBadge } from "@/components/ToneBadge";
import { overlayStack } from "@/lib/overlayStack";
import { api } from "@/lib/api";
import {
  SIM_DIFFICULTY_COPY,
  SIM_SCORING_LABELS,
  simAdvanceBlockers,
  simAdvanceWarnings,
  simDynastyProgressLine,
  simFmtPts,
  simFmtRecord,
  simGameGate,
  simLeagueTeamLabel,
  simGameDeleteFailure,
  simGameLiteLine,
  simGamePaywalled,
  simGameUnavailableCopy,
  simNewGameBlock,
  simSettingsSummary,
  simSetupAdvancedChanged,
  simSetupBlock,
  simSetupBody,
  simSetupCountOptions,
  simSetupDefaults,
  simSetupDynastyNote,
  simSetupModes,
  simSetupSummary,
  simSetupTaxiDefault,
  simStartNotice,
  simTeamNameChoices,
  simWeekHeading,
  SIM_NAME_CUSTOM,
  SIM_START_CONNECT_NOTE,
  SIM_START_LEAGUE_LABEL,
  SIM_START_LEAGUE_NOTE,
  SIM_START_NEW_LABEL,
  SIM_START_POINT_LABELS,
  SIM_START_POINT_NOTE,
  SIM_TEAM_NAME_MAX,
  SIM_TE_PREMIUM_LABELS,
  type SimDifficulty,
  type SimMode,
  type SimFlexType,
  type SimTiebreaker,
  SIM_FLEX_TYPE_LABELS,
  SIM_TIEBREAKER_LABELS,
  type SimDraftRecap,
  type SimGame,
  type SimGameCreateBody,
  type SimGameGate,
  type SimGameLite,
  type SimGameOptionsResponse,
  type SimGamePlayer,
  type SimGamePreview,
  type SimGameTone,
  type SimScoring,
  type SimSetupState,
  type SimStartPoint,
  type SimWaiverClaim,
  simTradeSeedFor,
  type SimTradeSeed,
  type SimToResponse,
  simSeasonText,
} from "@/lib/simGame";
import { simScrollKey, simShouldScrollTop } from "@/lib/simScroll";
import { simToProgressLabel, simToRemaining } from "@/lib/simTo";
import { SIM_FLOW_INITIAL, SIM_TABS, simFlowReducer, simRecapsFromAdvance, type SimTab } from "@/lib/simGameFlow";
import { useSimDeltaReload, useSimGameCall } from "@/lib/useSimGameCall";
import { useSimLeagueTeams } from "@/lib/useSimLeagueTeams";
import { useSimLeagueChoices } from "@/lib/useSimLeagueChoices";

const UPSELL_FALLBACK = {
  title: "Keep your season going with Pro",
  body: "The draft and your first 3 weeks are free. Pro unlocks the rest of the season, the playoffs and your final grade. Your save picks up right where you stopped.",
};

/** Fantasy Sim: the GM Game. Standalone and turn-based; see lib/simGame.ts and docs/fantasy-sim-game-design.md. */
export function SimGameContent() {
  const [flow, dispatch] = useReducer(simFlowReducer, SIM_FLOW_INITIAL);
  const [options, setOptions] = useState<SimGameOptionsResponse | null>(null);
  const [games, setGames] = useState<SimGameLite[]>([]);
  const [game, setGameState] = useState<SimGame | null>(null);
  const [preview, setPreview] = useState<SimGamePreview | null>(null);
  const [notice, setNotice] = useState<{ message: string; tone: SimGameTone } | null>(null);
  const [tick, setTick] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [sheetPlayer, setSheetPlayer] = useState<SimGamePlayer | null>(null);
  const [sheetTeam, setSheetTeam] = useState<string | null>(null);
  const [draftRecap, setDraftRecap] = useState<{ recap: SimDraftRecap | null } | null>(null);
  const [claims, setClaims] = useState<SimWaiverClaim[]>([]);
  const [tradeSeed, setTradeSeed] = useState<SimTradeSeed | null>(null);
  const [advancing, setAdvancing] = useState(false);
  const [simToOpen, setSimToOpen] = useState(false);
  const [simToResult, setSimToResult] = useState<SimToResponse | null>(null);
  const [simToRequest, setSimToRequest] = useState<SimToRequest | null>(null);
  const [simToBusy, setSimToBusy] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [managing, setManaging] = useState(false);

  // One overlay at a time (lib/overlayStack.ts): a player card opened from a trade picker / claim sheet replaces it on screen
  // and shows "‹ Back to ..." itself. `stackedUnder` (card opened from another pop-up) hides the card's trade shortcut.
  const overlayCount = useSyncExternalStore(overlayStack.subscribe, () => overlayStack.size(), () => 0);
  const stackedUnder = Boolean(sheetPlayer) && overlayCount > 1;

  // A new page (tab, recap, draft -> season, offseason step) starts at the top, instantly.
  const scrollKey = simScrollKey({ view: flow.view, stage: flow.stage, tab: flow.tab, recapIndex: flow.recapIndex, hasRecap: flow.recaps.length > 0, draftRecap: draftRecap !== null, week: game?.week ?? null, status: game?.status ?? null, step: game?.dynasty?.stage ?? null });
  const lastScrollKey = useRef<string | null>(null);
  useLayoutEffect(() => {
    if (simShouldScrollTop(lastScrollKey.current, scrollKey)) window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    lastScrollKey.current = scrollKey;
  }, [scrollKey]);

  const notify = useCallback((message: string, tone: SimGameTone = "warning") => setNotice(message ? { message, tone } : null), []);

  const onGate = useCallback(
    (gate: SimGameGate) => {
      dispatch({ type: "gate", gate });
      if (gate.kind === "premium" && gate.preview) setPreview(gate.preview);
      if (gate.kind === "blocked") notify(gate.message, "warning");
      if (gate.kind === "unavailable" && gate.cause === "busy") notify("The simulator is busy right now. Try again in a few seconds.", "warning");
    },
    [notify],
  );

  const gameId = flow.gameId;
  const fetchGame = useCallback(async () => {
    if (!gameId) return;
    try {
      const body = await api.getSimGame(gameId);
      if (body.game) {
        setGameState(body.game);
        dispatch({ type: "game_updated", game: body.game });
        if (body.preview !== undefined) setPreview(body.preview ?? null);
      }
    } catch {
      /* the next action reports the failure */
    }
  }, [gameId]);

  // A small action's own response already carries the header slice it changed (`delta`), so right after one
  // the screen applies that and confirms with the server in the background instead of waiting on a second request.
  const { onDelta, reloadGame } = useSimDeltaReload(fetchGame, setGameState);

  const call = useSimGameCall(
    onGate,
    (message) => notify(message, "danger"),
    () => {
      notify("The game changed somewhere else. We reloaded it. Try again.", "warning");
      void fetchGame();
      setTick((n) => n + 1);
    },
    onDelta,
  );

  // Hub data: options (works for Free) and the saved games.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const opts = await api.getSimGameOptions();
        if (cancelled) return;
        const gate = simGameGate(opts);
        if (gate.kind === "unavailable") {
          dispatch({ type: "gate", gate });
          return;
        }
        setOptions(opts);
        if (opts.preview !== undefined) setPreview(opts.preview ?? null);
        const list = await api.listSimGames();
        if (cancelled) return;
        const listGate = simGameGate(list);
        if (listGate.kind === "unavailable") {
          dispatch({ type: "gate", gate: listGate });
          return;
        }
        setGames(list.games ?? []);
        dispatch({ type: "hub" });
      } catch (error) {
        if (cancelled) return;
        const status = (error as { status?: number })?.status;
        if (status === 404) dispatch({ type: "gate", gate: { kind: "unavailable", cause: "off" } });
        else dispatch({ type: "error", message: error instanceof Error ? error.message : "Could not load Fantasy Sim." });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const refreshList = useCallback(async () => {
    try {
      const list = await api.listSimGames();
      setGames(list.games ?? []);
    } catch {
      /* best effort */
    }
  }, []);

  async function deleteSaved(id: string): Promise<boolean> {
    setDeletingId(id);
    let removed = false;
    try {
      const body = await api.deleteSimGame(id);
      const gate = simGameGate(body);
      if (gate.kind === "ready") {
        removed = true;
        notify("Game deleted.", "success");
      } else if (gate.kind === "blocked") {
        notify(gate.message, "warning");
      } else if (gate.kind === "unavailable" && gate.cause === "busy") {
        notify("The simulator is busy right now. Try again in a few seconds.", "warning");
      } else {
        notify("Could not delete the game. Try again.", "danger");
      }
    } catch (error) {
      const failure = simGameDeleteFailure(error);
      removed = failure.remove;
      notify(failure.message, failure.tone);
      if (failure.refresh) void refreshList();
    }
    setDeletingId(null);
    if (removed) {
      // Drop it right away so the count, the limit note and New game update with no reload.
      setGames((prev) => {
        const next = prev.filter((g) => g.id !== id);
        if (next.length === 0) setManaging(false);
        return next;
      });
      void refreshList();
    }
    return removed;
  }

  const openGame = useCallback(
    async (id: string) => {
      setNotice(null);
      const body = await call(() => api.getSimGame(id));
      if (body?.game) {
        setGameState(body.game);
        setPreview(body.preview ?? null);
        setClaims([]);
        setDraftRecap(null);
        dispatch({ type: "open", game: body.game });
      }
    },
    [call],
  );

  async function createGame(body: SimGameCreateBody) {
    setCreating(true);
    const res = await call(() => api.createSimGame(body));
    setCreating(false);
    if (res?.game) {
      setGameState(res.game);
      setPreview(res.preview ?? null);
      setClaims([]);
      dispatch({ type: "open", game: res.game });
      void refreshList();
      const heads = simStartNotice(res.game, body);
      if (heads) notify(heads);
    }
  }

  const setGame = useCallback((next: SimGame) => {
    setGameState(next);
    dispatch({ type: "game_updated", game: next });
  }, []);

  async function advance() {
    if (!game) return;
    const blockers = simAdvanceBlockers(game, preview);
    if (blockers.some((b) => b.code === "paywalled")) {
      dispatch({ type: "gate", gate: { kind: "premium", upsell: null, preview } });
      return;
    }
    if (blockers.length) {
      notify(blockers[0].message, "danger");
      dispatch({ type: "tab", tab: "team" });
      return;
    }
    setAdvancing(true);
    setNotice(null);
    const res = await call(() => api.advanceSimGame(game.id, game.week));
    setAdvancing(false);
    if (res?.recap && res.game) {
      setGameState(res.game);
      if (res.preview !== undefined) setPreview(res.preview ?? null);
      setClaims([]);
      dispatch({ type: "advanced", recaps: simRecapsFromAdvance(res.recap, res.also_played), game: res.game });
      setTick((n) => n + 1);
      void refreshList();
    }
  }

  async function runSimTo(request: SimToRequest) {
    if (!game) return;
    const blockers = simAdvanceBlockers(game, preview);
    if (blockers.some((b) => b.code === "paywalled")) {
      dispatch({ type: "gate", gate: { kind: "premium", upsell: null, preview } });
      return;
    }
    setAdvancing(true);
    setSimToRequest(request);
    setSimToBusy(request.option.label);
    setNotice(null);
    const res = await call(() => api.simToGame(game.id, { target: request.option.id, weeks: request.option.weeks, auto_set: request.autoSet, force_first: request.forceFirst, stops: request.stops }));
    setAdvancing(false);
    setSimToBusy(null);
    if (!res) return;
    if (res.game) {
      setGameState(res.game);
      if (res.preview !== undefined) setPreview(res.preview ?? null);
      if ((res.weeks_played ?? 0) > 0) {
        setClaims([]);
        dispatch({ type: "advanced", recaps: [], game: res.game });
        setTick((n) => n + 1);
        void refreshList();
      }
    }
    setSimToResult(res);
  }

  async function undoSimTo(): Promise<boolean> {
    const from = simToResult?.from_seq;
    if (!game || from == null) return false;
    const res = await call(() => api.undoSimTo(game.id, from));
    if (!res?.game) return false;
    setGameState(res.game);
    setClaims([]);
    dispatch({ type: "advanced", recaps: [], game: res.game });
    setTick((n) => n + 1);
    setSimToResult(null);
    notify("Took the simulated weeks back.", "success");
    void refreshList();
    return true;
  }

  const ctx: SimCtx | null = useMemo(
    () =>
      game
        ? {
            gameId: game.id,
            game,
            preview,
            call,
            setGame,
            reloadGame,
            notify,
            tick,
            bump: () => setTick((n) => n + 1),
            openPlayer: setSheetPlayer,
            openTeam: setSheetTeam,
          }
        : null,
    [game, preview, call, setGame, reloadGame, notify, tick],
  );

  // ----------------------------------------------------------------- views
  if (flow.view === "loading") {
    return (
      <Shell>
        <div className="flex flex-col gap-3" aria-busy="true">
          <span className="sr-only" role="status">Loading Fantasy Sim</span>
          <SkeletonCard lines={3} />
          <SkeletonCard lines={4} />
        </div>
      </Shell>
    );
  }
  if (flow.view === "unavailable") {
    const copy = simGameUnavailableCopy(flow.cause ?? "off");
    return (
      <Shell>
        <EmptyState
          title={copy.title}
          subtitle={copy.subtitle}
          actionLabel={flow.cause === "off" ? undefined : "Try again"}
          onAction={flow.cause === "off" ? undefined : () => { dispatch({ type: "hub" }); setAttempt((n) => n + 1); }}
        />
      </Shell>
    );
  }
  if (flow.view === "error") {
    return <ErrorState message={flow.message || "Could not load Fantasy Sim."} onRetry={() => { dispatch({ type: "setup" }); setAttempt((n) => n + 1); }} />;
  }

  if (flow.view === "setup") {
    return (
      <Shell>
        {flow.paywall ? <PaywallCard flow={flow} onDismiss={() => dispatch({ type: "dismiss_paywall" })} /> : null}
        {notice ? <SimNotice message={notice.message} tone={notice.tone} onDismiss={() => setNotice(null)} /> : null}
        <SetupForm options={options} creating={creating} onCreate={createGame} onBack={() => dispatch({ type: "hub" })} />
      </Shell>
    );
  }

  if (flow.view === "game" && game && ctx) {
    return (
      <Shell wide game>
        <GameScreen
          flow={flow}
          game={game}
          ctx={ctx}
          preview={preview}
          advancing={advancing}
          notice={notice}
          clearNotice={() => setNotice(null)}
          onAdvance={advance}
          onSimTo={() => setSimToOpen(true)}
          simToOpen={simToOpen}
          onSimToClose={() => setSimToOpen(false)}
          onRunSimTo={runSimTo}
          simToResult={simToResult}
          simToBusy={simToBusy}
          onSimToDone={() => setSimToResult(null)}
          onSimToForce={() => { if (simToRequest) { const played = simToResult?.weeks_played ?? 0; setSimToResult(null); void runSimTo({ ...simToRequest, option: simToRemaining(simToRequest.option, played), forceFirst: true }); } }}
          onSimToUndo={undoSimTo}
          onSimToGoPro={() => dispatch({ type: "gate", gate: { kind: "premium", upsell: null, preview } })}
          onTab={(tab) => dispatch({ type: "tab", tab })}
          draftRecap={draftRecap}
          onDraftComplete={(recap) => setDraftRecap({ recap })}
          onStartSeason={() => setDraftRecap(null)}
          claims={claims}
          setClaims={setClaims}
          tradeSeed={tradeSeed}
          setTradeSeed={setTradeSeed}
          onRecapNext={() => dispatch({ type: "recap_next" })}
          onRecapClose={() => dispatch({ type: "recap_close" })}
          onDismissPaywall={() => dispatch({ type: "dismiss_paywall" })}
          onHub={() => { dispatch({ type: "hub" }); setGameState(null); void refreshList(); }}
          onNewGame={() => { dispatch({ type: "setup" }); setGameState(null); }}
          onDeleted={() => { dispatch({ type: "deleted" }); setGameState(null); void refreshList(); }}
        />
        {sheetPlayer ? (
          <SimPlayerSheet
            gameId={game.id}
            startYear={game.settings.start_year}
            seasonLabel={game.dynasty ? simSeasonText(game.dynasty) : null}
            player={sheetPlayer}
            onClose={() => setSheetPlayer(null)}
            actions={
              <>
                {game.can_trade && !stackedUnder && simTradeSeedFor(sheetPlayer) ? (
                <Button
                  size="sm"
                  variant="secondary"
                  aria-label={`Add ${sheetPlayer.name} to trade`}
                  onClick={() => {
                    const seed = simTradeSeedFor(sheetPlayer);
                    if (!seed) return;
                    setTradeSeed(seed);
                    setSheetPlayer(null);
                    dispatch({ type: "tab", tab: "trades" });
                  }}
                >
                  Add to trade
                </Button>
              ) : null}
              <SimBlockToggle ctx={ctx} player={sheetPlayer} />
              </>
            }
          />
        ) : null}
        {sheetTeam ? (
          <SimTeamSheet
            ctx={ctx}
            teamId={sheetTeam}
            onClose={() => setSheetTeam(null)}
            onTrade={(partner) => {
              setSheetTeam(null);
              setTradeSeed({ partner, get: "" });
              dispatch({ type: "tab", tab: "trades" });
            }}
          />
        ) : null}
      </Shell>
    );
  }

  // hub
  const block = simNewGameBlock(games.length, options?.max_games ?? 1, options?.is_premium);
  return (
    <Shell>
      <SimPreviewBanner preview={preview} />
      {flow.paywall ? <PaywallCard flow={flow} onDismiss={() => dispatch({ type: "dismiss_paywall" })} /> : null}
      {notice ? <SimNotice message={notice.message} tone={notice.tone} onDismiss={() => setNotice(null)} /> : null}
      <AccentCard accent="var(--color-accent)" as="section" className="enter-rise">
        <p className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>Sandbox</p>
        <p className="text-lg font-extrabold">Be the GM. Win the season.</p>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Draft a 12-team league against AI managers, set your lineup, work waivers and trades week by week, and take on the playoffs. At the end you get a grade. Nothing here touches your real leagues.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={Boolean(block)} onClick={() => dispatch({ type: "setup" })}>New game</Button>
          {block && options?.is_premium === false ? <ButtonLink href="/premium" variant="premiumOutline" size="sm">Go Pro</ButtonLink> : null}
          {block ? (
            <Button variant="secondary" size="sm" onClick={() => { setManaging(true); document.getElementById("sim-saved-games")?.scrollIntoView?.({ behavior: "smooth", block: "start" }); }}>
              Manage games / delete one
            </Button>
          ) : null}
        </div>
        {block ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="new-game-block">{block}</p>
        ) : null}
      </AccentCard>
      <section id="sim-saved-games" className="flex flex-col gap-2" aria-label="Your games">
        <SectionHeading note={games.length ? (managing ? "Tap the trash can on a game to delete it." : undefined) : "Your saved games show up here."}>Your games</SectionHeading>
        {games.length === 0 ? (
          <EmptyState title="No games yet" subtitle="Start a new game to draft your team." />
        ) : (
          games.map((g) => (
            <div key={g.id} className="flex flex-col gap-1.5">
              <div className="relative flex items-stretch gap-2">
                <button type="button" className="flex-1 min-w-0 text-left" onClick={() => void openGame(g.id)} aria-label={`Open game: ${simGameLiteLine(g)}`}>
                  <SavedGameCard game={g} />
                </button>
                <ConfirmInPlace
                  variant="icon"
                  overlay="parent"
                  label={`Delete game: ${simGameLiteLine(g)}`}
                  prompt="Delete this game? It can't be undone."
                  confirmLabel="Delete"
                  keepLabel="Keep"
                  errorText="Could not delete it. Try again."
                  disabled={deletingId !== null}
                  onConfirm={() => deleteSaved(g.id)}
                />
              </div>
            </div>
          ))
        )}
      </section>
    </Shell>
  );
}

function SavedGameCard({ game }: { game: SimGameLite }) {
  const row = simHubRow(game);
  const tone = row.chip.tone;
  const done = game.status === "complete";
  return (
    <AccentCard accent={done ? simToneColor(tone) : "var(--color-accent)"} compact as="div">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex min-w-0 items-center gap-2">
          <span style={{ color: simToneColor(tone) }}><SimGlyph name={done ? "check" : game.status === "drafting" ? "team" : "standings"} size={16} /></span>
          <span className="text-sm font-bold truncate">{row.title}</span>
        </span>
        <ToneBadge label={row.chip.label} color={simToneColor(tone)} size="xs" />
      </div>
      {row.progress ? <SimProgressBar done={row.progress.done} total={row.progress.total} tone={tone} label={`${row.progress.done} of ${row.progress.total} weeks played`} /> : null}
      <div className="flex items-center justify-between gap-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
        <span className="min-w-0 truncate">{row.meta}</span>
        <span className="shrink-0">{row.played}{row.open ? <span className="font-bold" style={{ color: "var(--color-accent)" }}>{row.played ? " · " : ""}Continue</span> : null}</span>
      </div>
    </AccentCard>
  );
}

function Shell({ children, wide = false, game = false }: { children: React.ReactNode; wide?: boolean; game?: boolean }) {
  return (
    // `game`: on phones the in-game screen owns the whole viewport (its own compact header on top, bottom tab bar
    // in flow at the bottom of a 100dvh column), so no outer padding or gap.
    <main className={`sim-root flex-auto flex flex-col gap-3 px-4 py-3 w-full mx-auto ${game ? "max-md:min-h-dvh max-md:pt-0 max-md:pb-0 max-md:gap-0" : ""} ${wide ? "max-w-5xl xl:max-w-[1200px]" : "max-w-3xl"}`}>
      {game ? null : <SimExitBar />}
      <PageTitle page="Fantasy Sim" />
      {children}
    </main>
  );
}

/**
 * Phone-only way out of the Fantasy Sim's hub, setup and error screens. The sim owns the phone chrome
 * (lib/bottomNav pathOwnsPhoneChrome hides the global header, GM orb and shell bar for the whole /gm-game
 * path), but only the in-game screen draws its own header and orb, so these screens had no navigation at
 * all. Back returns to wherever the user came from (a league page, More, Portfolio), else Home.
 */
function SimExitBar() {
  const router = useRouter();
  return (
    <nav className="md:hidden flex items-center justify-between gap-2" aria-label="Leave Fantasy Sim" data-testid="sim-exit-bar">
      <button
        type="button"
        className="tap-link text-sm font-bold"
        style={{ color: "var(--color-accent)", minHeight: 44 }}
        onClick={() => (typeof window !== "undefined" && window.history.length > 1 ? router.back() : router.push("/"))}
      >
        ‹ Back
      </button>
      <Link href="/" className="tap-link text-sm font-bold" style={{ color: "var(--color-accent)", minHeight: 44, display: "inline-flex", alignItems: "center" }}>
        Home
      </Link>
    </nav>
  );
}

function PaywallCard({ flow, onDismiss }: { flow: typeof SIM_FLOW_INITIAL; onDismiss: () => void }) {
  return (
    <div className="flex flex-col gap-2 enter-rise" data-testid="sim-paywall">
      <PremiumUpsellCard
        bare
        kicker="Fantasy Sim"
        upsell={flow.paywall?.upsell ?? null}
        fallbackTitle={UPSELL_FALLBACK.title}
        fallbackBody={UPSELL_FALLBACK.body}
      />
      <Button variant="ghost" size="sm" onClick={onDismiss}>Keep looking around</Button>
    </div>
  );
}

function SetupForm({
  options,
  creating,
  onCreate,
  onBack,
}: {
  options: SimGameOptionsResponse | null;
  creating: boolean;
  onCreate: (body: SimGameCreateBody) => void;
  onBack: () => void;
}) {
  const opts = options?.options;
  const defaults = useMemo(() => simSetupDefaults(options), [options]);
  const [state, setState] = useState<SimSetupState>(defaults);
  const set = <K extends keyof SimSetupState>(key: K, value: SimSetupState[K]) => setState((prev) => ({ ...prev, [key]: value }));
  const league = state.start === "league";
  const leagueMode = options?.start_modes?.find((m) => m.id === "league");
  const canImport = leagueMode ? leagueMode.available : false;
  const leagues = useSimLeagueChoices(state.start === "league");
  const leagueTeams = useSimLeagueTeams(league ? state.leagueId : "", (rosterId) => set("rosterId", rosterId));
  const nameChoices = simTeamNameChoices(options);
  const modes = simSetupModes(options);
  const dynasty = state.mode === "dynasty";
  const dynastyNote = simSetupDynastyNote(state);
  const changed = simSetupAdvancedChanged(state, defaults);
  const block = simSetupBlock(state);
  const [tab, setTab] = useState<SimSetupTab>("quick");
  const nameLabel = nameChoices.find((choice) => choice.value === state.nameChoice)?.label ?? "";
  const summaries = simSetupCardSummaries(state, state.nameChoice === SIM_NAME_CUSTOM ? state.name.trim() : nameLabel);
  const custom = tab === "custom";
  const detail = `${simSetupSummary(state, options?.layout)} ${options?.season ? `${options.season.regular_weeks}-week season, then ${options.season.playoff_teams}-team playoffs. Trade deadline week ${options.season.trade_deadline_week}.` : ""}`.trim();
  const cardCount = custom ? 6 : 3;
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!block) onCreate(simSetupBody(state));
      }}
    >
      <SectionHeading note="Quick start is one tap. Customize to change the league. Nothing can be changed once the game starts.">New game</SectionHeading>
      <PillRow
        ariaLabel="Setup mode"
        variant="fill"
        options={SIM_SETUP_TABS.map((t) => ({ label: t.label, value: t.key, count: t.key === "custom" && changed ? changed : undefined }))}
        active={tab}
        onSelect={(value) => setTab(value as SimSetupTab)}
      />
      <SetupSummaryCard headline={simSetupHeadline(state)} chips={simSetupChips(state)} detail={detail} testId="sim-setup-summary" />
      <SetupCard id="start" summary={summaries.start} index={0} count={cardCount}>
        {canImport && (custom || league) ? (
          <SetupField label="Starting point" note={league ? SIM_START_LEAGUE_NOTE : undefined}>
            <PillRow
              ariaLabel="Starting point"
              variant="fill"
              options={[{ label: SIM_START_NEW_LABEL, value: "fresh" }, { label: SIM_START_LEAGUE_LABEL, value: "league" }]}
              active={state.start}
              onSelect={(value) => set("start", value as SimSetupState["start"])}
            />
          </SetupField>
        ) : null}
        {league && leagues !== null && leagues.length === 0 ? (
          <div className="flex flex-col gap-2 items-start" data-testid="sim-connect-in-option">
            <SetupNote>{SIM_START_CONNECT_NOTE}</SetupNote>
            <ButtonLink href="/connect-league" variant="secondary" size="sm">Connect a Sleeper league</ButtonLink>
          </div>
        ) : null}
        {league && (leagues === null || leagues.length > 0) ? (
          <label className="flex flex-col gap-2 text-sm font-bold">
            Your league
            <Select value={state.leagueId} onChange={(event) => setState((prev) => ({ ...prev, leagueId: event.target.value, rosterId: "" }))} aria-label="League to start from" disabled={leagues === null}>
              <option value="">{leagues === null ? "Loading your leagues..." : "Choose a league"}</option>
              {(leagues ?? []).map((row) => (
                <option key={row.league_id} value={row.league_id}>{row.league_name || row.league_id}</option>
              ))}
            </Select>
          </label>
        ) : null}
        {league && state.leagueId ? (
          <div className="flex flex-col gap-2" data-testid="sim-team-picker">
            <label className="flex flex-col gap-2 text-sm font-bold">
              Your team
              <Select
                value={state.rosterId}
                onChange={(event) => set("rosterId", event.target.value)}
                aria-label="Your team in this league"
                disabled={leagueTeams.status !== "ready"}
              >
                <option value="">
                  {leagueTeams.status === "loading" ? "Loading teams..." : leagueTeams.status === "error" ? "Teams unavailable" : "Choose your team"}
                </option>
                {leagueTeams.status === "ready"
                  ? leagueTeams.teams.map((team) => (
                      <option key={team.roster_id} value={team.roster_id}>
                        {simLeagueTeamLabel(team)}
                        {team.is_you ? " (you)" : ""}
                      </option>
                    ))
                  : null}
              </Select>
            </label>
            {leagueTeams.status === "error" ? (
              <p className="text-[13px]" role="status" style={{ color: "var(--color-warning)" }}>{leagueTeams.message}</p>
            ) : leagueTeams.status === "ready" && !leagueTeams.youRosterId ? (
              <SetupNote>We could not tell which team is yours from your Sleeper link. Pick it from the list.</SetupNote>
            ) : null}
            <SetupField label="Start from" note={SIM_START_POINT_NOTE}>
              <PillRow
                ariaLabel="Start from"
                variant="fill"
                options={(opts?.start_point?.values ?? ["preseason", "current"]).map((v) => ({ label: SIM_START_POINT_LABELS[v], value: v }))}
                active={state.startPoint}
                onSelect={(value) => set("startPoint", value as SimStartPoint)}
              />
            </SetupField>
          </div>
        ) : null}
        {!league ? (
          <div className="flex flex-col gap-2">
            <label className="flex flex-col gap-2 text-sm font-bold">
              Your team name
              <Select value={state.nameChoice} onChange={(event) => set("nameChoice", event.target.value)} aria-label="Your team name">
                {nameChoices.map((choice) => (
                  <option key={choice.value} value={choice.value}>{choice.label}</option>
                ))}
              </Select>
            </label>
            {state.nameChoice === SIM_NAME_CUSTOM ? (
              <Input value={state.name} maxLength={SIM_TEAM_NAME_MAX} placeholder="My Team" aria-label="Custom team name" onChange={(event) => set("name", event.target.value)} />
            ) : null}
          </div>
        ) : null}
      </SetupCard>
      <SetupCard id="difficulty" summary={summaries.difficulty} index={1} count={cardCount}>
        <DifficultyTiles values={(opts?.difficulty.values ?? ["easy", "normal", "hard"]) as SimDifficulty[]} active={state.difficulty} onSelect={(value) => set("difficulty", value)} />
        <SetupNote>{SIM_DIFFICULTY_FOOTNOTE}</SetupNote>
      </SetupCard>
      {custom ? (
        <>
          <SetupCard id="format" summary={summaries.format} index={2} count={cardCount}>
            {modes.length > 1 ? (
              <SetupField label="Game mode">
                <PillRow ariaLabel="Game mode" variant="fill" options={modes} active={state.mode} onSelect={(value) => set("mode", value as SimMode)} />
              </SetupField>
            ) : null}
            {dynasty ? (
              <>
                <SetupField label="Seasons" note="How many seasons you play. Each one ends with an offseason.">
                  <PillRow
                    ariaLabel="Seasons"
                    variant="fill"
                    options={(opts?.seasons?.values ?? [3, 4, 5]).map((n) => ({ label: String(n), value: String(n) }))}
                    active={String(state.seasons)}
                    onSelect={(value) => set("seasons", Number(value))}
                  />
                </SetupField>
                <SetupField label="Rookie draft rounds">
                  <PillRow
                    ariaLabel="Rookie draft rounds"
                    variant="fill"
                    options={(opts?.rookie_rounds?.values ?? [2, 3, 4, 5]).map((n) => ({ label: String(n), value: String(n) }))}
                    active={String(state.rookieRounds)}
                    onSelect={(value) => set("rookieRounds", Number(value))}
                  />
                </SetupField>
              </>
            ) : null}
            {dynastyNote ? <SetupNote testId="sim-dynasty-note">{dynastyNote}</SetupNote> : null}
          </SetupCard>
          <SetupCard id="league" summary={summaries.league} index={3} count={cardCount}>
            {!league ? (
              <>
                <SetupField label="League size" note={`You plus ${state.teams - 1} AI managers.`}>
                  <PillRow
                    ariaLabel="League size"
                    variant="fill"
                    options={(opts?.teams.values ?? [8, 10, 12, 14]).map((n) => ({ label: `${n} teams`, value: String(n) }))}
                    active={String(state.teams)}
                    onSelect={(value) => setState((prev) => ({ ...prev, teams: Number(value), slot: "" }))}
                  />
                </SetupField>
                <SetupField label="Scoring">
                  <PillRow
                    ariaLabel="Scoring"
                    variant="fill"
                    options={(opts?.scoring.values ?? ["ppr", "half", "std"]).map((sc) => ({ label: SIM_SCORING_LABELS[sc], value: sc }))}
                    active={state.scoring}
                    onSelect={(value) => set("scoring", value as SimScoring)}
                  />
                </SetupField>
                <SetupField label="TE premium">
                  <PillRow
                    ariaLabel="TE premium"
                    variant="fill"
                    options={(opts?.te_premium?.values ?? [0, 0.5, 1]).map((v) => ({ label: SIM_TE_PREMIUM_LABELS[v] ?? `+${v}`, value: String(v) }))}
                    active={String(state.tePremium)}
                    onSelect={(value) => set("tePremium", Number(value))}
                  />
                </SetupField>
                <SetupField label="Flex spot" note="Who can start in the FLEX slot. RB / WR / TE is the standard.">
                  <PillRow
                    ariaLabel="Flex spot"
                    variant="fill"
                    options={(opts?.flex_type?.values ?? ["flex", "rb_wr"]).map((v) => ({ label: SIM_FLEX_TYPE_LABELS[v], value: v }))}
                    active={state.flexType}
                    onSelect={(value) => set("flexType", value as SimFlexType)}
                  />
                </SetupField>
                <SetupToggleGroup>
                  <SetupToggleRow first label="Superflex" note="A second quarterback can start in an extra flex slot." checked={state.superflex} onChange={(v) => set("superflex", v)} />
                  <SetupToggleRow label="Kicker" note="Start a K." checked={state.includeK} onChange={(v) => set("includeK", v)} />
                  <SetupToggleRow label="Defense (DEF)" note="Start a team defense (estimated from points allowed)." checked={state.includeDef} onChange={(v) => set("includeDef", v)} />
                </SetupToggleGroup>
                <SetupField label="Tiebreaker" note="Breaks equal records in standings and playoff seeding.">
                  <PillRow
                    ariaLabel="Tiebreaker"
                    variant="fill"
                    options={(opts?.tiebreaker?.values ?? ["points_for", "head_to_head"]).map((v) => ({ label: SIM_TIEBREAKER_LABELS[v], value: v }))}
                    active={state.tiebreaker}
                    onSelect={(value) => set("tiebreaker", value as SimTiebreaker)}
                  />
                </SetupField>
              </>
            ) : (
              <SetupNote>Size, scoring, lineup and rosters come from your Sleeper league.</SetupNote>
            )}
          </SetupCard>
          <SetupCard id="extras" summary={summaries.extras} index={4} count={cardCount}>
            {!league ? (
              <>
                <SetupField label="Bench size" id="sim-bench-label">
                  <PillRow
                    ariaLabel="Bench size"
                    variant="scroll"
                    options={Array.from({ length: (opts?.bench?.max ?? 10) - (opts?.bench?.min ?? 4) + 1 }, (_, i) => String((opts?.bench?.min ?? 4) + i)).map((n) => ({ label: n, value: n }))}
                    active={String(state.bench)}
                    onSelect={(value) => set("bench", Number(value))}
                  />
                </SetupField>
                <label className="flex flex-col gap-2 text-sm font-bold">
                  Draft position
                  <Select value={state.slot} onChange={(event) => set("slot", event.target.value)} aria-label="Draft position">
                    <option value="">Random</option>
                    {Array.from({ length: state.teams }, (_, i) => (
                      <option key={i + 1} value={String(i + 1)}>
                        Pick {i + 1}
                      </option>
                    ))}
                  </Select>
                </label>
              </>
            ) : null}
            <SetupField label="IR slots" note="Injured players stash here and do not use a roster spot.">
              <PillRow
                ariaLabel="IR slots"
                variant="scroll"
                options={simSetupCountOptions(opts?.ir_slots?.max ?? 4, opts?.ir_slots?.default ?? null, opts?.ir_slots?.min ?? 0)}
                active={state.irSlots == null ? "" : String(state.irSlots)}
                onSelect={(value) => set("irSlots", value === "" ? null : Number(value))}
              />
            </SetupField>
            <SetupField label="Taxi slots" note="Young players stash here and do not score or use a roster spot.">
              <PillRow
                ariaLabel="Taxi slots"
                variant="scroll"
                options={simSetupCountOptions(opts?.taxi_slots?.max ?? 8, simSetupTaxiDefault(options, state.mode), opts?.taxi_slots?.min ?? 0)}
                active={state.taxiSlots == null ? "" : String(state.taxiSlots)}
                onSelect={(value) => set("taxiSlots", value === "" ? null : Number(value))}
              />
            </SetupField>
            <SetupField label="Taxi eligibility" note="Who can go on the taxi squad: rookies only, or players in their first 2, 3 or 4 years.">
              <PillRow
                ariaLabel="Taxi eligibility"
                variant="fill"
                options={[{ label: "Default", value: "" }, ...(opts?.taxi_years?.values ?? [1, 2, 3, 4]).map((n) => ({ label: n === 1 ? "Rookies" : `${n} years`, value: String(n) }))]}
                active={state.taxiYears == null ? "" : String(state.taxiYears)}
                onSelect={(value) => set("taxiYears", value === "" ? null : Number(value))}
              />
            </SetupField>
          </SetupCard>
        </>
      ) : null}
      <MotionIn index={custom ? 5 : 2} count={cardCount}>
        <section className="glass-surface p-4 min-w-0" aria-label="Lineup management">
          <SetupToggleGroup>
            <SetupToggleRow first label="Auto-set my lineup" note="Starts your best healthy players each week. You can still change it." checked={state.auto} onChange={(v) => set("auto", v)} />
          </SetupToggleGroup>
        </section>
      </MotionIn>
      <SetupStickyBar warning={block}>
        <Button type="button" variant="ghost" onClick={onBack}>Back</Button>
        <Button type="submit" className="flex-1 glass-start" fullWidth loading={creating} disabled={Boolean(block)}>{league ? "Start the season" : "Start the draft"}</Button>
      </SetupStickyBar>
    </form>
  );
}

function GameScreen({
  flow,
  game,
  ctx,
  preview,
  advancing,
  notice,
  clearNotice,
  onAdvance,
  onSimTo,
  simToOpen,
  onSimToClose,
  onRunSimTo,
  simToResult,
  simToBusy,
  onSimToDone,
  onSimToForce,
  onSimToUndo,
  onSimToGoPro,
  onTab,
  draftRecap,
  onDraftComplete,
  onStartSeason,
  claims,
  setClaims,
  tradeSeed,
  setTradeSeed,
  onRecapNext,
  onRecapClose,
  onDismissPaywall,
  onHub,
  onNewGame,
  onDeleted,
}: {
  flow: typeof SIM_FLOW_INITIAL;
  game: SimGame;
  ctx: SimCtx;
  preview: SimCtx["preview"];
  advancing: boolean;
  notice: { message: string; tone: SimGameTone } | null;
  clearNotice: () => void;
  onAdvance: () => void;
  onSimTo: () => void;
  simToOpen: boolean;
  onSimToClose: () => void;
  onRunSimTo: (request: SimToRequest) => void;
  simToResult: SimToResponse | null;
  simToBusy: string | null;
  onSimToDone: () => void;
  onSimToForce: () => void;
  onSimToUndo: () => Promise<boolean>;
  onSimToGoPro: () => void;
  onTab: (tab: SimTab) => void;
  draftRecap: { recap: SimDraftRecap | null } | null;
  onDraftComplete: (recap: SimDraftRecap | null) => void;
  onStartSeason: () => void;
  claims: SimWaiverClaim[];
  setClaims: (claims: SimWaiverClaim[]) => void;
  tradeSeed: SimTradeSeed | null;
  setTradeSeed: (seed: SimTradeSeed | null) => void;
  onRecapNext: () => void;
  onRecapClose: () => void;
  onDismissPaywall: () => void;
  onHub: () => void;
  onNewGame: () => void;
  onDeleted: () => void;
}) {
  const paywalled = simGamePaywalled(preview);
  const notif = useSimNotifications(ctx);
  const stage = flow.stage;
  const recap = flow.recaps[flow.recapIndex];
  const warnings = simAdvanceWarnings(game);
  const youLine = game.you;
  const inSeason = (stage === "week" || stage === "playoffs") && !draftRecap;
  const showBar = inSeason && !recap && !simToResult;
  const showOffBar = stage === "offseason" && !draftRecap && !recap;
  const [moreOpen, setMoreOpen] = useState(false);
  // Phones: the game orb (docked above the Advance pill) is the page navigator; the top PillRows render from md up.
  const showOrb = showBar || showOffBar;
  const orbNode = showOrb ? (
    <SimGameOrb
              tab={flow.tab}
              offseason={stage === "offseason"}
              inbox={game.pending?.inbox ?? 0}
              onTab={onTab}
              onMore={() => setMoreOpen(true)}
              onHub={onHub}
            />
  ) : null;

  return (
    <SimTeamOpenContext.Provider value={ctx.openTeam}>
    <SimOpenPlayerContext.Provider value={ctx.openPlayer}>
    {/* Phones: a 100dvh flex column. Compact header on top, content flex-1, and the action pill + bottom tab bar as an in-flow
        sticky footer (no position:fixed, no JS placement), so iOS Safari viewport quirks cannot float it. */}
    <div className={`flex flex-auto flex-col gap-3 max-md:gap-2 ${showBar || showOffBar ? "pb-3 max-md:pb-0" : "pb-6"} md:pb-3`}>
      <SimGameHeader game={game} onHub={onHub} onTeam={(id) => ctx.openTeam(id)} onMore={() => setMoreOpen(true)} bell={<SimNotificationBell notif={notif} onOpenTab={onTab} />} />
      <div className="hidden items-center justify-between gap-2 md:flex">
        <div className="flex min-w-0 flex-col">
          <button type="button" className="tap-link text-xs font-bold self-start" style={{ color: "var(--color-accent)" }} onClick={onHub}>
            All games
          </button>
          <h2 className="text-lg font-extrabold break-words" data-testid="game-heading">{simWeekHeading(game)}</h2>
          {game.dynasty ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="dynasty-progress">{simDynastyProgressLine(game.dynasty)}</p>
          ) : null}
          {youLine && stage !== "draft" ? (
            <div className="flex flex-wrap items-center gap-x-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
              <SimTeamLink teamId={youLine.team_id} name={youLine.name} size={20} bold={false} />
              <span>{simFmtRecord(youLine)}{youLine.rank ? ` · #${youLine.rank}` : ""} · {simFmtPts(youLine.pf)} PF</span>
            </div>
          ) : null}
        </div>
        <SimNotificationBell notif={notif} onOpenTab={onTab} />
      </div>

      <SimPreviewBanner preview={preview} />
      {flow.paywall ? <PaywallCard flow={flow} onDismiss={onDismissPaywall} /> : null}
      {notice ? <SimNotice message={notice.message} tone={notice.tone} onDismiss={clearNotice} /> : null}
      {inSeason && !recap && !paywalled && warnings.length > 0 ? (
        <ul className="hidden flex-col gap-0.5 text-xs md:flex" style={{ color: "var(--color-text-muted)" }} aria-label="Before you advance">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}
      {inSeason && !recap && !paywalled ? <SimStatusChips game={game} onTab={onTab} /> : null}

      {stage === "draft" ? (
        <SimGameDraft ctx={ctx} onComplete={onDraftComplete} />
      ) : draftRecap ? (
        <SimDraftRecapView recap={draftRecap.recap} ctx={ctx} onStart={onStartSeason} />
      ) : simToResult ? (
        <SimToResultView result={simToResult} onClose={onSimToDone} onTab={(tab) => onTab(tab)} onForce={onSimToForce} onUndo={onSimToUndo} onGoPro={onSimToGoPro} />
      ) : recap ? (
        <SimWeekRecapStory recap={recap} index={flow.recapIndex} total={flow.recaps.length} ctx={ctx} onNext={onRecapNext} onClose={onRecapClose} onFixLineup={() => { onRecapClose(); onTab("team"); }} />
      ) : stage === "final" ? (
        <SimFinalView ctx={ctx} onNewGame={onNewGame} onHub={onHub} />
      ) : stage === "offseason" ? (
        <>
          <PillRow
            className="max-md:hidden"
            ariaLabel="Offseason sections"
            variant="fill"
            sticky
            options={[
              { label: "Offseason", value: "home" },
              { label: "Team", value: "team" },
              { label: "Trades", value: "trades" },
              { label: "League", value: "league" },
            ]}
            active={["team", "trades", "league"].includes(flow.tab) ? flow.tab : "home"}
            onSelect={(value) => onTab(value as SimTab)}
          />
          <div key={flow.tab} className="enter-rise flex-auto max-md:pb-16">
            {flow.tab === "team" ? <SimTeamTab ctx={ctx} onTrade={() => onTab("trades")} /> : null}
            {flow.tab === "trades" ? <SimTradesTab ctx={ctx} seed={tradeSeed} onSeedUsed={() => setTradeSeed(null)} /> : null}
            {flow.tab === "league" ? <SimLeagueTab ctx={ctx} /> : null}
            {["team", "trades", "league"].includes(flow.tab) ? null : <SimGameOffseason ctx={ctx} onTrade={() => onTab("trades")} onTeam={() => onTab("team")} />}
          </div>
        </>
      ) : (
        <>
          <PillRow
            className="max-md:hidden"
            ariaLabel="Game sections"
            variant="fill"
            sticky
            options={SIM_TABS.map((t) => ({ label: t.label, value: t.value, glyph: t.glyph, count: t.value === "trades" ? game.pending?.inbox ?? 0 : undefined }))}
            active={flow.tab}
            onSelect={(value) => onTab(value as SimTab)}
          />
          <div key={flow.tab} className="enter-rise flex-auto max-md:pb-16">
            {flow.tab === "home" ? <SimHomeTab ctx={ctx} setClaims={setClaims} onTab={onTab} /> : null}
            {flow.tab === "team" ? <SimTeamTab ctx={ctx} onTrade={() => onTab("trades")} /> : null}
            {flow.tab === "players" ? (
              <SimPlayersTab
                ctx={ctx}
                claims={claims}
                setClaims={setClaims}
                onTradeFor={(player) => {
                  if (player.owner?.team_id) setTradeSeed({ partner: player.owner.team_id, get: player.id });
                  onTab("trades");
                }}
              />
            ) : null}
            {flow.tab === "trades" ? <SimTradesTab ctx={ctx} seed={tradeSeed} onSeedUsed={() => setTradeSeed(null)} /> : null}
            {flow.tab === "league" ? <SimLeagueTab ctx={ctx} /> : null}
            {flow.tab === "more" ? <SimMoreTab ctx={ctx} onDeleted={onDeleted} onHub={onHub} /> : null}
          </div>
        </>
      )}
      <div className="bottom-stack" data-testid="sim-bottom-stack">
        {showOffBar ? <SimOffseasonBar ctx={ctx} onTab={onTab} orb={orbNode} /> : null}
        {showBar ? <SimActionBar ctx={ctx} paywalled={paywalled} advancing={advancing} onAdvance={onAdvance} onSimTo={onSimTo} onTab={onTab} orb={orbNode} /> : null}
      </div>
      <SimToSheet ctx={ctx} open={simToOpen} onClose={onSimToClose} onRun={onRunSimTo} />
      {simToBusy ? (
        <div className="fixed inset-x-0 bottom-24 z-40 mx-auto flex w-fit max-w-[90vw] items-center gap-2 glass-surface px-4 py-2 text-sm font-bold" role="status" aria-live="polite" data-testid="sim-to-progress">
          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
          {simToProgressLabel(simToBusy)}
        </div>
      ) : null}
      <Sheet open={moreOpen} onClose={() => setMoreOpen(false)} title="Game menu" description="Rules, reset the week, or leave this game.">
        <SimMoreTab ctx={ctx} onDeleted={() => { setMoreOpen(false); onDeleted(); }} onHub={() => { setMoreOpen(false); onHub(); }} />
      </Sheet>
    </div>
    </SimOpenPlayerContext.Provider>
    </SimTeamOpenContext.Provider>
  );
}

function SimMoreTab({ ctx, onDeleted, onHub }: { ctx: SimCtx; onDeleted: () => void; onHub: () => void }) {
  const { game, gameId, call } = ctx;
  const s = game.settings;

  async function revert(): Promise<boolean> {
    const body = await call(() => api.revertSimWeek(gameId));
    if (!body?.game) return false;
    ctx.setGame(body.game);
    ctx.bump();
    ctx.notify(body.reverted ? "This week's decisions were reset." : "Nothing to reset this week.", "success");
    return true;
  }
  async function remove(): Promise<boolean> {
    const body = await call(() => api.deleteSimGame(gameId));
    if (!body) return false;
    onDeleted();
    return true;
  }

  return (
    <div className="flex flex-col gap-2">
      {(() => {
        const h = simMenuHero(game, SIM_DIFFICULTY_COPY[s.difficulty].label, SIM_SCORING_LABELS[s.scoring] ?? String(s.scoring));
        return <Hero label={h.label} value={h.value} context={h.context} tone="accent" testId="sim-menu-hero" />;
      })()}
      <CompactModule
        id="sim.menu.week"
        title="This week"
        parts={[{ key: "u", text: "Undo lineup edits, claims, cuts and trades", strong: true }, { key: "n", text: "not an advanced week", tone: "muted" }]}
        tone="warning"
        persist={false}
      >
        <p className="text-sm">Undo this week&apos;s lineup edits, claims, cuts and trades back to how the week started. You cannot undo a week you already advanced.</p>
        <ConfirmInPlace label="Reset this week" buttonVariant="secondary" size="sm" onConfirm={revert} />
      </CompactModule>

      <CompactModule id="sim.menu.rules" title="League rules" parts={simRulesParts(s)} tone="muted" defaultOpen>
        <ul className="flex flex-col gap-2 text-sm">
          {([
            ["stats", "accent", `${simSettingsSummary(s)} · ${SIM_DIFFICULTY_COPY[s.difficulty].label}`],
            ["lineup", "success", `Starters: ${s.slots.join(", ")} · roster limit ${s.roster_limit}`],
            ["trophy", "warning", `${s.regular_weeks}-week season, ${s.playoff_teams}-team playoffs. Trade deadline: week ${s.trade_deadline_week}.`],
            ["waiver", "accent", "Waiver claims resolve when you advance, before games are scored, worst record first."],
          ] as const).map(([glyph, tone, text]) => (
            <li key={glyph} className="flex items-start gap-2">
              <ReviewGlyphChip glyph={glyph} tone={tone} size={24} />
              <span className="flex-1 min-w-0">{text}</span>
            </li>
          ))}
        </ul>
      </CompactModule>

      <CompactModule id="sim.menu.game" title="Game" parts={[{ key: "a", text: "All games", strong: true }, { key: "d", text: "Delete this game", tone: "danger" as const }]} tone="danger" persist={false} defaultOpen>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={onHub}>All games</Button>
        <ConfirmInPlace
          variant="button"
          mode="ask"
          size="sm"
          label="Delete game"
          prompt="Delete this game?"
          confirmLabel="Delete"
          errorText="Could not delete it. Try again."
          onConfirm={remove}
        />
      </div>
      </CompactModule>
    </div>
  );
}
