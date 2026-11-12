"use client";

import { useCallback, useEffect, useMemo, useReducer, useState } from "react";

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
import { SimPlayerSheet } from "@/components/SimGamePlayers";
import { SimNotice, SimPreviewBanner, type SimCtx } from "@/components/SimGameParts";
import { SimFinalView, SimWeekRecapView } from "@/components/SimGameRecap";
import { SimPlayersTab, SimTeamTab } from "@/components/SimGameTeam";
import { SimTradesTab } from "@/components/SimGameTrades";
import { SkeletonCard } from "@/components/Skeleton";
import { Toggle } from "@/components/Toggle";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import {
  SIM_DIFFICULTY_COPY,
  SIM_SCORING_LABELS,
  simAdvanceBlockers,
  simAdvanceLabel,
  simAdvanceWarnings,
  simFmtPts,
  simFmtRecord,
  simGameGate,
  simGameLiteLine,
  simGamePaywalled,
  simGameUnavailableCopy,
  simNewGameBlock,
  simSettingsSummary,
  simSetupAdvancedChanged,
  simSetupBlock,
  simSetupBody,
  simSetupDefaults,
  simSetupSummary,
  simWeekHeading,
  SIM_TE_PREMIUM_LABELS,
  type SimDifficulty,
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
  type SimWaiverClaim,
} from "@/lib/simGame";
import { SIM_FLOW_INITIAL, SIM_TABS, simFlowReducer, simRecapsFromAdvance, type SimTab } from "@/lib/simGameFlow";
import { useSimGameCall } from "@/lib/useSimGameCall";
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
  const [draftRecap, setDraftRecap] = useState<{ recap: SimDraftRecap | null } | null>(null);
  const [claims, setClaims] = useState<SimWaiverClaim[]>([]);
  const [tradeSeed, setTradeSeed] = useState<{ partner: string; get: string } | null>(null);
  const [advancing, setAdvancing] = useState(false);
  const [creating, setCreating] = useState(false);

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
  const reloadGame = useCallback(async () => {
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

  const call = useSimGameCall(
    onGate,
    (message) => notify(message, "danger"),
    () => {
      notify("The game changed somewhere else. We reloaded it. Try again.", "warning");
      void reloadGame();
      setTick((n) => n + 1);
    },
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
      <Shell wide>
        <GameScreen
          flow={flow}
          game={game}
          ctx={ctx}
          preview={preview}
          advancing={advancing}
          notice={notice}
          clearNotice={() => setNotice(null)}
          onAdvance={advance}
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
        {sheetPlayer ? <SimPlayerSheet gameId={game.id} player={sheetPlayer} onClose={() => setSheetPlayer(null)} /> : null}
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
          {block ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="new-game-block">{block}</span>
          ) : null}
          {block && options?.is_premium === false ? <ButtonLink href="/premium" variant="premiumOutline" size="sm">Go Pro</ButtonLink> : null}
        </div>
      </AccentCard>
      <section className="flex flex-col gap-2" aria-label="Your games">
        <SectionHeading note={games.length ? undefined : "Your saved games show up here."}>Your games</SectionHeading>
        {games.length === 0 ? (
          <EmptyState title="No games yet" subtitle="Start a new game to draft your team." />
        ) : (
          games.map((g) => (
            <button key={g.id} type="button" className="w-full text-left" onClick={() => void openGame(g.id)} aria-label={`Open game: ${simGameLiteLine(g)}`}>
              <AccentCard accent={g.status === "complete" ? "var(--color-success)" : "var(--color-accent)"} compact as="div">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-bold">{simGameLiteLine(g)}</span>
                  {g.grade_letter ? <ToneBadge label={g.grade_letter} color="var(--color-success)" size="xs" /> : <span className="text-xs" style={{ color: "var(--color-accent)" }}>Continue</span>}
                </div>
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {simSettingsSummary(g.settings) || `${SIM_SCORING_LABELS[(g.settings.scoring ?? "ppr") as SimScoring]} · ${g.settings.teams ?? 12} teams`} · {SIM_DIFFICULTY_COPY[g.difficulty]?.label ?? g.difficulty}
                </p>
              </AccentCard>
            </button>
          ))
        )}
      </section>
    </Shell>
  );
}

function Shell({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <main className={`flex-1 flex flex-col gap-3 px-4 py-3 w-full mx-auto ${wide ? "max-w-5xl" : "max-w-3xl"}`}>
      <PageTitle page="Fantasy Sim" />
      {children}
    </main>
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
  const leagueMode = options?.start_modes?.find((m) => m.id === "league");
  const canImport = leagueMode ? leagueMode.available : false;
  const leagues = useSimLeagueChoices(state.start === "league");
  const changed = simSetupAdvancedChanged(state, defaults);
  const block = simSetupBlock(state);
  const league = state.start === "league";
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!block) onCreate(simSetupBody(state));
      }}
    >
      <SectionHeading note="Quick start is 12 teams, half PPR and a standard lineup. You can change nothing after the game starts.">New game</SectionHeading>
      {canImport ? (
        <div className="flex flex-col gap-1">
          <span className="text-sm font-semibold">How to start</span>
          <PillRow
            ariaLabel="How to start"
            variant="fill"
            options={[{ label: "Fresh league", value: "fresh" }, { label: "My league", value: "league" }]}
            active={state.start}
            onSelect={(value) => set("start", value as SimSetupState["start"])}
          />
        </div>
      ) : null}
      {league ? (
        <label className="flex flex-col gap-1 text-sm font-semibold">
          Start from
          <Select value={state.leagueId} onChange={(event) => set("leagueId", event.target.value)} aria-label="League to start from" disabled={leagues === null}>
            <option value="">{leagues === null ? "Loading your leagues..." : leagues.length ? "Choose a league" : "No Sleeper leagues saved"}</option>
            {(leagues ?? []).map((row) => (
              <option key={row.league_id} value={row.league_id}>{row.league_name || row.league_id}</option>
            ))}
          </Select>
        </label>
      ) : null}
      <label className="flex flex-col gap-1 text-sm font-semibold">
        Your team name
        <Input value={state.name} maxLength={40} placeholder={league ? "Your team's real name" : "My Team"} onChange={(event) => set("name", event.target.value)} />
      </label>
      <div className="flex flex-col gap-1">
        <span className="text-sm font-semibold">Difficulty</span>
        <PillRow
          ariaLabel="Difficulty"
          variant="fill"
          options={(opts?.difficulty.values ?? ["easy", "normal", "hard"]).map((d) => ({ label: SIM_DIFFICULTY_COPY[d].label, value: d }))}
          active={state.difficulty}
          onSelect={(value) => set("difficulty", value as SimDifficulty)}
        />
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{SIM_DIFFICULTY_COPY[state.difficulty].blurb} Your own scoring is the same at every level.</p>
      </div>
      {!league ? (
        <details className="flex flex-col gap-4" data-testid="sim-advanced">
          <summary className="text-sm font-semibold cursor-pointer" style={{ minHeight: "var(--touch-target-min)" }}>
            Advanced options{changed ? ` (${changed} changed)` : ""}
          </summary>
          <div className="flex flex-col gap-4 pt-2">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold">League size</span>
              <PillRow
                ariaLabel="League size"
                variant="fill"
                options={(opts?.teams.values ?? [8, 10, 12, 14]).map((n) => ({ label: `${n} teams`, value: String(n) }))}
                active={String(state.teams)}
                onSelect={(value) => setState((prev) => ({ ...prev, teams: Number(value), slot: "" }))}
              />
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>You plus {state.teams - 1} AI managers.</p>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold">Scoring</span>
              <PillRow
                ariaLabel="Scoring"
                variant="fill"
                options={(opts?.scoring.values ?? ["ppr", "half", "std"]).map((s) => ({ label: SIM_SCORING_LABELS[s], value: s }))}
                active={state.scoring}
                onSelect={(value) => set("scoring", value as SimScoring)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold">TE premium</span>
              <PillRow
                ariaLabel="TE premium"
                variant="fill"
                options={(opts?.te_premium?.values ?? [0, 0.5, 1]).map((v) => ({ label: SIM_TE_PREMIUM_LABELS[v] ?? `+${v}`, value: String(v) }))}
                active={String(state.tePremium)}
                onSelect={(value) => set("tePremium", Number(value))}
              />
            </div>
            <SetupToggle label="Superflex" note="A second quarterback can start in an extra flex slot." checked={state.superflex} onChange={(v) => set("superflex", v)} />
            <SetupToggle label="Kicker" note="Start a K." checked={state.includeK} onChange={(v) => set("includeK", v)} />
            <SetupToggle label="Defense (DEF)" note="Start a team defense (estimated from points allowed)." checked={state.includeDef} onChange={(v) => set("includeDef", v)} />
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold" id="sim-bench-label">Bench size</span>
              <PillRow
                ariaLabel="Bench size"
                variant="scroll"
                options={Array.from({ length: (opts?.bench?.max ?? 10) - (opts?.bench?.min ?? 4) + 1 }, (_, i) => String((opts?.bench?.min ?? 4) + i)).map((n) => ({ label: n, value: n }))}
                active={String(state.bench)}
                onSelect={(value) => set("bench", Number(value))}
              />
            </div>
            <label className="flex flex-col gap-1 text-sm font-semibold">
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
          </div>
        </details>
      ) : null}
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col">
          <span className="text-sm font-semibold">Auto-set my lineup</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Starts your best healthy players each week. You can still change it.</span>
        </div>
        <Toggle checked={state.auto} onChange={(v) => set("auto", v)} label="Auto-set my lineup" />
      </div>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="sim-setup-summary">
        {simSetupSummary(state, options?.layout)} {options?.season ? `${options.season.regular_weeks}-week season, then ${options.season.playoff_teams}-team playoffs. Trade deadline week ${options.season.trade_deadline_week}.` : ""}
      </p>
      {block ? <p className="text-xs" role="status" style={{ color: "var(--color-warning)" }}>{block}</p> : null}
      <div className="flex gap-2">
        <Button type="submit" loading={creating} disabled={Boolean(block)}>{league ? "Start the season" : "Start the draft"}</Button>
        <Button type="button" variant="ghost" onClick={onBack}>Back</Button>
      </div>
    </form>
  );
}

function SetupToggle({ label, note, checked, onChange }: { label: string; note: string; checked: boolean; onChange: (next: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex flex-col">
        <span className="text-sm font-semibold">{label}</span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{note}</span>
      </div>
      <Toggle checked={checked} onChange={onChange} label={label} />
    </div>
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
  onTab: (tab: SimTab) => void;
  draftRecap: { recap: SimDraftRecap | null } | null;
  onDraftComplete: (recap: SimDraftRecap | null) => void;
  onStartSeason: () => void;
  claims: SimWaiverClaim[];
  setClaims: (claims: SimWaiverClaim[]) => void;
  tradeSeed: { partner: string; get: string } | null;
  setTradeSeed: (seed: { partner: string; get: string } | null) => void;
  onRecapNext: () => void;
  onRecapClose: () => void;
  onDismissPaywall: () => void;
  onHub: () => void;
  onNewGame: () => void;
  onDeleted: () => void;
}) {
  const paywalled = simGamePaywalled(preview);
  const stage = flow.stage;
  const recap = flow.recaps[flow.recapIndex];
  const warnings = simAdvanceWarnings(game);
  const youLine = game.you;
  const inSeason = (stage === "week" || stage === "playoffs") && !draftRecap;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-col">
          <button type="button" className="tap-link text-xs font-bold self-start" style={{ color: "var(--color-accent)" }} onClick={onHub}>
            All games
          </button>
          <h2 className="text-lg font-extrabold break-words" data-testid="game-heading">{simWeekHeading(game)}</h2>
          {youLine && stage !== "draft" ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {youLine.name} · {simFmtRecord(youLine)}{youLine.rank ? ` · #${youLine.rank}` : ""} · {simFmtPts(youLine.pf)} PF
            </p>
          ) : null}
        </div>
        {inSeason && !recap ? (
          paywalled ? (
            <ButtonLink href="/premium" variant="premium" size="sm">Go Pro to continue</ButtonLink>
          ) : (
            <Button loading={advancing} onClick={onAdvance} aria-label={simAdvanceLabel(game)}>
              {game.phase === "playoffs" ? "Play round" : "Advance week"}
            </Button>
          )
        ) : null}
      </div>

      <SimPreviewBanner preview={preview} />
      {flow.paywall ? <PaywallCard flow={flow} onDismiss={onDismissPaywall} /> : null}
      {notice ? <SimNotice message={notice.message} tone={notice.tone} onDismiss={clearNotice} /> : null}
      {inSeason && !recap && !paywalled && warnings.length > 0 ? (
        <ul className="flex flex-col gap-0.5 text-xs" style={{ color: "var(--color-text-muted)" }} aria-label="Before you advance">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}

      {stage === "draft" ? (
        <SimGameDraft ctx={ctx} onComplete={onDraftComplete} />
      ) : draftRecap ? (
        <SimDraftRecapView recap={draftRecap.recap} ctx={ctx} onStart={onStartSeason} />
      ) : recap ? (
        <SimWeekRecapView recap={recap} index={flow.recapIndex} total={flow.recaps.length} ctx={ctx} onNext={onRecapNext} onClose={onRecapClose} />
      ) : stage === "final" ? (
        <SimFinalView ctx={ctx} onNewGame={onNewGame} onHub={onHub} />
      ) : (
        <>
          <PillRow
            ariaLabel="Game sections"
            variant="fill"
            sticky
            options={SIM_TABS.map((t) => ({ label: t.value === "trades" && (game.pending?.inbox ?? 0) > 0 ? `Trades ${game.pending?.inbox}` : t.label, value: t.value }))}
            active={flow.tab}
            onSelect={(value) => onTab(value as SimTab)}
          />
          <div key={flow.tab} className="enter-rise">
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
    </div>
  );
}

function SimMoreTab({ ctx, onDeleted, onHub }: { ctx: SimCtx; onDeleted: () => void; onHub: () => void }) {
  const { game, gameId, call } = ctx;
  const [confirm, setConfirm] = useState<"revert" | "delete" | null>(null);
  const [busy, setBusy] = useState(false);
  const s = game.settings;

  async function revert() {
    setBusy(true);
    const body = await call(() => api.revertSimWeek(gameId));
    setBusy(false);
    setConfirm(null);
    if (body?.game) {
      ctx.setGame(body.game);
      ctx.bump();
      ctx.notify(body.reverted ? "This week's decisions were reset." : "Nothing to reset this week.", "success");
    }
  }
  async function remove() {
    setBusy(true);
    const body = await call(() => api.deleteSimGame(gameId));
    setBusy(false);
    if (body) onDeleted();
  }

  return (
    <div className="flex flex-col gap-3">
      <SectionHeading>This week</SectionHeading>
      <AccentCard accent="var(--color-warning)" compact as="div">
        <p className="text-sm">Undo this week&apos;s lineup edits, claims, cuts and trades back to how the week started. You cannot undo a week you already advanced.</p>
        {confirm === "revert" ? (
          <div className="flex gap-2">
            <Button size="sm" variant="danger" loading={busy} onClick={revert}>Reset this week</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
          </div>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => setConfirm("revert")}>Reset this week</Button>
        )}
      </AccentCard>

      <SectionHeading>League rules</SectionHeading>
      <AccentCard accent="var(--color-border-strong)" compact as="div">
        <ul className="flex flex-col gap-1 text-sm">
          <li>{simSettingsSummary(s)} · {SIM_DIFFICULTY_COPY[s.difficulty].label}</li>
          <li>Starters: {s.slots.join(", ")} · roster limit {s.roster_limit}</li>
          <li>{s.regular_weeks}-week season, {s.playoff_teams}-team playoffs. Trade deadline: week {s.trade_deadline_week}.</li>
          <li>Waiver claims resolve when you advance, worst record first.</li>
        </ul>
      </AccentCard>

      <SectionHeading>Game</SectionHeading>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" onClick={onHub}>All games</Button>
        {confirm === "delete" ? (
          <>
            <Button size="sm" variant="danger" loading={busy} onClick={remove}>Delete this game</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>Keep it</Button>
          </>
        ) : (
          <Button size="sm" variant="dangerOutline" onClick={() => setConfirm("delete")}>Delete game</Button>
        )}
      </div>
    </div>
  );
}
