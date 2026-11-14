"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { SectionHeading } from "@/components/SectionHeading";
import { SimDraftBoard } from "@/components/SimDraftBoard";
import { SimDraftGlyph } from "@/components/SimDraftGlyphs";
import { SimDraftOverview } from "@/components/SimDraftOverview";
import { SimDraftHero } from "@/components/SimDraftHero";
import { SimIconButton, SimPlayerChip, SimPlayerLine, SimStat, SimToneBadge, useSimWide, type SimCtx } from "@/components/SimGameParts";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { CompactModule } from "@/components/ui/CompactModule";
import { api } from "@/lib/api";
import { simDraftNeedPills, simDraftSummaryParts } from "@/lib/simDraft";
import {
  SIM_QUEUE_MAX,
  simFmtPts,
  simProjText,
  simQueueReducer,
  simFilterPositionsFor,
  simPositionsFor,
  simRosterNeeds,
  simValueOverAdpLabel,
  simValueOverAdpTone,
  type SimDraftHint,
  type SimDraftPick,
  type SimDraftRecap,
  type SimDraftState,
  type SimGamePlayer,
} from "@/lib/simGame";
import { playerSurname } from "@/lib/playerNameDisplay";

type Panel = "board" | "queue" | "roster" | "picks";

/**
 * The draft room: ONE compact clock module (a dense status line with the pick action, expanding to needs, best
 * available and auto-pick), who has been drafted (recent picks + mini board) always on the page, and ONE tab row:
 * Players (search, one filter/sort row), your queue, your roster by need and the pick log. There is no pick clock. A
 * pick resolves every AI pick up to your next turn in one call.
 */
export function SimGameDraft({ ctx, onComplete }: { ctx: SimCtx; onComplete: (recap: SimDraftRecap | null) => void }) {
  const { gameId, game, call } = ctx;
  const wide = useSimWide();
  const [draft, setDraft] = useState<SimDraftState | null>(null);
  const [hint, setHint] = useState<SimDraftHint | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [queue, dispatchQueue] = useReducer(simQueueReducer, { ids: [] });
  const [players, setPlayers] = useState<Record<string, SimGamePlayer>>({});
  const [panel, setPanel] = useState<Panel>("board");
  const [busy, setBusy] = useState<"pick" | "auto" | null>(null);
  // Optimistic pick: the player the user just tapped, shown as drafted until the server answers.
  const [optimistic, setOptimistic] = useState<SimGamePlayer | null>(null);
  const pickInFlight = useRef(false);
  const [confirmAuto, setConfirmAuto] = useState(false);
  const [freshPickNos, setFreshPickNos] = useState<number[]>([]);
  const [attempt, setAttempt] = useState(0);
  const queueLoaded = useRef(false);

  // The first load, and after a conflict/retry.
  useEffect(() => {
    let cancelled = false;
    api
      .getSimDraft(gameId, "page=1&page_size=1")
      .then((body) => {
        if (cancelled) return;
        if (body.reason) {
          ctx.notify(body.message ?? "Could not load the draft.", "danger");
          setLoadState("error");
          return;
        }
        setDraft(body.draft ?? null);
        setHint(body.hint ?? null);
        dispatchQueue({ type: "set", ids: body.draft?.queue ?? [] });
        queueLoaded.current = true;
        if (body.draft) rememberPlayers(body.draft.your_roster, body.draft.picks);
        setLoadState("ready");
      })
      .catch(() => {
        if (!cancelled) setLoadState("error");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, attempt]);

  function rememberPlayers(roster: SimGamePlayer[] | undefined, picks: SimDraftPick[] | undefined) {
    setPlayers((prev) => {
      const next = { ...prev };
      for (const p of roster ?? []) next[p.id] = p;
      for (const pick of picks ?? []) next[pick.player.id] = pick.player;
      return next;
    });
  }

  // Persist the queue shortly after it changes (auto-pick reads it server-side).
  const saved = useRef<string>("");
  useEffect(() => {
    if (!queueLoaded.current) return;
    const key = queue.ids.join(",");
    if (key === saved.current) return;
    const id = setTimeout(() => {
      saved.current = key;
      void call(() => api.putSimDraftQueue(gameId, queue.ids));
    }, 500);
    return () => clearTimeout(id);
  }, [queue.ids, gameId, call]);

  const applyResult = useCallback(
    (body: { picks?: SimDraftPick[]; draft?: Partial<SimDraftState>; completed?: boolean; recap?: SimDraftRecap | null; game?: typeof game }) => {
      const made = body.picks ?? [];
      setDraft((prev) => {
        if (!prev) return prev;
        const merged = { ...prev, ...(body.draft ?? {}) } as SimDraftState;
        merged.picks = [...(prev.picks ?? []), ...made];
        return merged;
      });
      rememberPlayers(body.draft?.your_roster, made);
      setFreshPickNos(made.map((m) => m.pick_no));
      if (made.length) dispatchQueue({ type: "prune", taken: made.map((m) => m.player.id) });
      if (body.game) ctx.setGame(body.game);
      ctx.bump();
      if (body.completed) onComplete(body.recap ?? null);
    },
    [ctx, onComplete],
  );

  async function pick(player: SimGamePlayer) {
    // A ref, not state: two taps in the same frame must still submit once.
    if (busy || pickInFlight.current) return;
    pickInFlight.current = true;
    setBusy("pick");
    setOptimistic(player);
    const body = await call(() => api.simDraftPick(gameId, player.id, draft?.pick_no));
    setBusy(null);
    pickInFlight.current = false;
    if (body) {
      applyResult(body);
      setOptimistic(null);
      // Refresh the hint for the next turn.
      api
        .getSimDraft(gameId, "page=1&page_size=1")
        .then((next) => setHint(next.hint ?? null))
        .catch(() => {});
    } else {
      // Rejected (player_taken / already_picked / conflict): roll the row back and reload a fresh board.
      setOptimistic(null);
      ctx.notify("That pick did not go through. The board was refreshed.", "danger");
      setAttempt((n) => n + 1);
      ctx.bump();
    }
  }

  async function autoDraft() {
    setConfirmAuto(false);
    setBusy("auto");
    const body = await call(() => api.simDraftAuto(gameId));
    setBusy(null);
    if (body) applyResult(body);
  }

  const teamNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const t of draft?.teams ?? []) map[t.team_id] = t.is_you ? `${t.name} (you)` : t.name;
    return map;
  }, [draft?.teams]);

  if (loadState === "loading") {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <SkeletonCard lines={3} />
        <SkeletonCard lines={5} />
      </div>
    );
  }
  if (loadState === "error" || !draft) {
    return <EmptyState title="Could not load the draft" subtitle="Check your connection and try again." actionLabel="Try again" onAction={() => { setLoadState("loading"); setAttempt((n) => n + 1); }} />;
  }

  const onClock = Boolean(draft.on_the_clock?.is_you) && draft.status === "in_progress";
  const queued = queue.ids.map((id) => players[id]).filter(Boolean);
  const picks = draft.picks ?? [];
  const recent = [...picks].reverse().slice(0, 40);
  const needs = simRosterNeeds(draft.your_roster, game.settings.slots);

  /** ONE trailing action: Draft while you are on the clock. The Queue toggle is a small chip at the end of the chips line. */
  const boardActions = (player: SimGamePlayer) =>
    onClock ? (
      <SimIconButton size={44} width={48} label={`Draft ${player.name}`} primary busy={busy === "pick"} onClick={() => pick(player)}>
        <SimDraftGlyph name="draft" />
      </SimIconButton>
    ) : null;
  const boardChipsExtra = (player: SimGamePlayer) => {
    const inQueue = queue.ids.includes(player.id);
    return (
      <button
        type="button"
        aria-pressed={inQueue}
        aria-label={inQueue ? `Remove ${player.name} from queue` : `Queue ${player.name}`}
        className="inline-flex items-center gap-1 rounded-full px-2 text-[0.6875rem] font-bold"
        style={{ minHeight: 24, color: inQueue ? "var(--color-accent)" : "var(--color-text-secondary)", background: inQueue ? "var(--color-accent-soft)" : "var(--glass-input-bg)" }}
        onClick={() => {
          setPlayers((prev) => ({ ...prev, [player.id]: player }));
          dispatchQueue({ type: inQueue ? "remove" : "add", id: player.id });
        }}
      >
        <SimDraftGlyph name={inQueue ? "queued" : "queue"} />
        {inQueue ? "Queued" : "Queue"}
      </button>
    );
  };

  const board = (
    <SimDraftBoard
      gameId={gameId}
      positions={simFilterPositionsFor(game.settings.slots)}
      week={game.week}
      draftedIds={optimistic ? [optimistic.id] : undefined}
      onOpen={ctx.openPlayer}
      actions={boardActions}
      chipsExtra={boardChipsExtra}
      refreshKey={ctx.tick}
      onItems={(items) => setPlayers((prev) => ({ ...prev, ...Object.fromEntries(items.map((p) => [p.id, p])) }))}
    />
  );

  const side = (which: Exclude<Panel, "board">) => {
    if (which === "queue") {
      return (
        <section className="flex flex-col gap-2" aria-label="Your queue">
          <SectionHeading note={`Auto-pick drafts from the top of your queue first. ${queue.ids.length}/${SIM_QUEUE_MAX}`}>Queue</SectionHeading>
          {queued.length === 0 ? (
            <EmptyState title="Nothing queued" subtitle="Tap Queue on any player to line up your picks." />
          ) : (
            queued.map((player, index) => (
              <SimPlayerLine
                key={player.id}
                player={player}
                onOpen={ctx.openPlayer}
                trailing={
                  <div className="flex items-center gap-1">
                    <Button size="sm" variant="ghost" aria-label={`Move ${player.name} up`} disabled={index === 0} onClick={() => dispatchQueue({ type: "move", id: player.id, delta: -1 })}>
                      <SimDraftGlyph name="up" />
                    </Button>
                    <Button size="sm" variant="ghost" aria-label={`Move ${player.name} down`} disabled={index === queued.length - 1} onClick={() => dispatchQueue({ type: "move", id: player.id, delta: 1 })}>
                      <SimDraftGlyph name="down" />
                    </Button>
                    <Button size="sm" variant="ghost" aria-label={`Remove ${player.name}`} onClick={() => dispatchQueue({ type: "remove", id: player.id })}>
                      <SimDraftGlyph name="remove" />
                    </Button>
                    {onClock ? (
                      <Button size="sm" loading={busy === "pick"} onClick={() => pick(player)} aria-label={`Draft ${player.name}`}>
                        <SimDraftGlyph name="draft" />
                        <span className="ml-1">Draft</span>
                      </Button>
                    ) : null}
                  </div>
                }
              />
            ))
          )}
        </section>
      );
    }
    if (which === "roster") {
      return (
        <section className="flex flex-col gap-2" aria-label="Your roster">
          <SectionHeading note={`Starters: ${game.settings.slots.join(", ")}.`}>Your roster</SectionHeading>
          <ul className="grid gap-2" style={{ gridTemplateColumns: `repeat(${needs.length}, minmax(0, 1fr))` }} aria-label="Roster needs">
            {needs.map((n) => (
              <li key={n.pos} className="glass-surface p-2 text-center">
                <p className="text-xs font-bold">{n.pos}</p>
                <p className="text-sm font-extrabold" style={{ color: n.have >= n.starters ? "var(--color-success)" : "var(--color-warning)" }}>
                  {n.have}/{n.starters}
                </p>
              </li>
            ))}
          </ul>
          {draft.your_roster.length === 0 ? (
            <EmptyState title="No picks yet" subtitle="Your drafted players show up here." />
          ) : (
            draft.your_roster.map((player) => (
              <SimPlayerLine key={player.id} player={player} onOpen={ctx.openPlayer} trailing={<SimStat label="Proj" value={simProjText(player)} />} />
            ))
          )}
        </section>
      );
    }
    return (
      <section className="flex flex-col gap-2" aria-label="Pick log">
        <SectionHeading note="Newest first. Steal and reach compare a pick to its ADP.">Picks</SectionHeading>
        {recent.length === 0 ? (
          <EmptyState title="No picks yet" subtitle="Picks show up here as the draft moves." />
        ) : (
          recent.map((pk) => (
            <div key={pk.pick_no} className={freshPickNos.includes(pk.pick_no) ? "enter-rise" : undefined}>
              <SimPlayerLine
                player={pk.player}
                onOpen={ctx.openPlayer}
                extra={
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    #{pk.pick_no} · {teamNames[pk.team_id] ?? "Team"}
                  </span>
                }
                trailing={
                  pk.value_over_adp != null && simValueOverAdpLabel(pk.value_over_adp) ? (
                    <SimToneBadge label={simValueOverAdpLabel(pk.value_over_adp)} tone={simValueOverAdpTone(pk.value_over_adp)} />
                  ) : null
                }
              />
            </div>
          ))
        )}
      </section>
    );
  };

  const need = simDraftNeedPills(draft.your_roster, game.settings.slots);
  const draftLast = hint ? playerSurname(hint.player.name) : "";
  const header = (
    <CompactModule
      id="draft.clock"
      title={draft.status === "complete" ? "Draft" : "Draft clock"}
      testId="draft-clock-module"
      tone={onClock ? "action" : "accent"}
      glow={onClock}
      persist={false}
      parts={simDraftSummaryParts(draft, game.settings.teams, need, { picking: Boolean(optimistic) })}
      action={
        onClock && hint ? (
          <Button size="sm" loading={busy === "pick"} onClick={() => pick(hint.player)}>
            Draft {draftLast}
          </Button>
        ) : null
      }
    >
      {onClock && hint ? (
        <div className="flex flex-col gap-1 enter-rise" data-testid="draft-hint">
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{hint.why}</p>
          <SimPlayerChip player={hint.player} extra={hint.player.overall != null ? <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>OVR {hint.player.overall}</span> : undefined} />
        </div>
      ) : null}
      <SimDraftHero gameId={gameId} draft={draft} teams={game.settings.teams} slots={game.settings.slots} positions={simPositionsFor(game.settings.slots)} tick={ctx.tick} onOpen={ctx.openPlayer} />
      <div className="flex flex-wrap items-center gap-2">
        {confirmAuto ? (
          <>
            <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>Auto-draft the rest of your picks from your queue, then best available and need?</span>
            <Button size="sm" onClick={autoDraft}>Yes, auto-pick</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirmAuto(false)}>Cancel</Button>
          </>
        ) : (
          <Button size="sm" variant="secondary" loading={busy === "auto"} disabled={draft.status === "complete" || busy === "pick"} onClick={() => setConfirmAuto(true)}>
            Auto-pick the rest
          </Button>
        )}
      </div>
    </CompactModule>
  );

  const sidePanel = (wide ? (panel === "board" ? "queue" : panel) : panel) as Exclude<Panel, "board">;
  const tabs = [
    ...(wide ? [] : [{ label: "Players", value: "board", glyph: "players" as const }]),
    { label: `Queue${queue.ids.length ? ` ${queue.ids.length}` : ""}`, value: "queue", glyph: "queue" as const },
    { label: "Roster", value: "roster", glyph: "roster" as const },
    { label: "Picks", value: "picks", glyph: "picks" as const },
  ];
  const activeTab = wide && panel === "board" ? "queue" : panel;

  return (
    <div className="flex flex-col gap-3">
      {header}
      <SimDraftOverview draft={draft} teams={game.settings.teams} onOpen={ctx.openPlayer} />
      <PillRow ariaLabel="Draft panels" variant="fill" options={tabs} active={activeTab} onSelect={(value) => setPanel(value as Panel)} />
      {wide ? (
        <div className="grid gap-4" style={{ gridTemplateColumns: "minmax(0, 3fr) minmax(0, 2fr)" }}>
          <div>{board}</div>
          <div>{side(sidePanel)}</div>
        </div>
      ) : panel === "board" ? (
        board
      ) : (
        side(panel as Exclude<Panel, "board">)
      )}
    </div>
  );
}

/** The draft recap: team grades with your best/worst pick, then "Start the season". */
export function SimDraftRecapView({ recap, ctx, onStart }: { recap: SimDraftRecap | null; ctx: SimCtx; onStart: () => void }) {
  const teams = [...(recap?.teams ?? [])].sort((a, b) => b.starter_projection - a.starter_projection);
  const mine = recap?.your_team ?? teams.find((t) => t.is_you) ?? null;
  const nameOf = (pick: unknown) => (pick as { player?: SimGamePlayer } | null | undefined)?.player;
  return (
    <div className="flex flex-col gap-3 enter-rise" data-testid="draft-recap">
      <AccentCard accent="var(--color-success)" as="section">
        <p className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>Draft complete</p>
        <p className="text-lg font-extrabold">Your team is set for Week 1.</p>
        {mine ? (
          <div className="flex items-center gap-3">
            <ToneBadge label={`Draft grade ${mine.grade}`} color="var(--color-success)" />
            <span className="text-sm">Starters project {simFmtPts(mine.starter_projection)} a week.</span>
          </div>
        ) : null}
        {nameOf(mine?.best_pick) ? (
          <div className="flex flex-col gap-1">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Best pick</span>
            <SimPlayerChip player={nameOf(mine?.best_pick)!} />
          </div>
        ) : null}
        {nameOf(mine?.worst_pick) ? (
          <div className="flex flex-col gap-1">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Biggest reach</span>
            <SimPlayerChip player={nameOf(mine?.worst_pick)!} />
          </div>
        ) : null}
        <Button onClick={onStart}>Start the season</Button>
      </AccentCard>
      {teams.length > 0 ? (
        <section className="flex flex-col gap-2" aria-label="Team draft grades">
          <SectionHeading note="Graded on how strong each team's starting lineup projects.">How every team drafted</SectionHeading>
          {teams.map((team, index) => (
            <AccentCard key={team.team_id} accent={team.is_you || team.team_id === ctx.game.you?.team_id ? "var(--color-accent)" : "var(--color-border-strong)"} compact as="div">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-bold break-words min-w-0">{index + 1}. {team.name}</span>
                <span className="flex items-center gap-2 shrink-0">
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{simFmtPts(team.starter_projection)}</span>
                  <ToneBadge label={team.grade} color="var(--color-accent)" size="xs" />
                </span>
              </div>
            </AccentCard>
          ))}
        </section>
      ) : null}
    </div>
  );
}
