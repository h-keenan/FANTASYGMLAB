"use client";

import { useCallback, useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { SimDraftRow } from "@/components/SimDraftBoard";
import { SimDynastyStrip } from "@/components/SimGameDynasty";
import { SimCollapse, SimGeneratedChip, SimGeneratedNoticeSheet, SimPickLine, SimPlayerChips, SimRookieNoticeGate, useSimPicks } from "@/components/SimGameDynastyParts";
import { SimPlayerLine, SimStat, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { SimReserveButton, SimReserveGroups, SimReserveSheet } from "@/components/SimGameReserves";
import { SkeletonCard } from "@/components/Skeleton";
import { api } from "@/lib/api";
import {
  simArchiveToYear,
  simFmtPts,
  simMoverText,
  simOffseasonCta,
  simOffseasonHeading,
  simOffseasonProgressLine,
  simOffseasonSteps,
  simOrdinal,
  simPicksOf,
  simPlayoffOutcomeTone,
  simPlayoffResultLabel,
  simPositionsFor,
  simReservesOn,
  simRetireesSorted,
  simRookieClassChip,
  simRookieClockLine,
  simRookiePickLine,
  type SimDynastyYear,
  type SimGamePlayer,
  type SimOffseason,
  type SimOffseasonResponse,
  type SimPos,
  type SimTeamRosterResponse,
} from "@/lib/simGame";

type Busy = "start" | "pick" | "auto" | "season" | null;

/**
 * The dynasty offseason, one screen per stage. Review (last season, retirees,
 * aging, your picks), the rookie draft (the board of available rookies), and
 * the roster check before the next season. Each block is collapsible with a
 * summary line first, and the one big button sits at the bottom of the screen.
 */
export function SimGameOffseason({ ctx, onTrade, onTeam }: { ctx: SimCtx; onTrade: () => void; onTeam: () => void }) {
  const { gameId, call } = ctx;
  const [off, setOff] = useState<SimOffseason | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [pos, setPos] = useState<SimPos | "">("");
  const [busy, setBusy] = useState<Busy>(null);
  const [confirmAuto, setConfirmAuto] = useState(false);
  const [years, setYears] = useState<SimDynastyYear[]>([]);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimOffseason(gameId, pos)
      .then((body) => {
        if (cancelled) return;
        if (body.offseason) {
          setOff(body.offseason);
          setState("ready");
        } else {
          setState("error");
        }
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, pos, ctx.tick, attempt]);

  // The per-year strip: every finished season (GET /dynasty), loaded once.
  useEffect(() => {
    let cancelled = false;
    api
      .getSimDynasty(gameId)
      .then((body) => {
        if (!cancelled && body.dynasty) setYears(body.dynasty.by_year ?? []);
      })
      .catch(() => {
        /* the strip is optional */
      });
    return () => {
      cancelled = true;
    };
  }, [gameId]);

  const apply = useCallback(
    (body: SimOffseasonResponse) => {
      if (body.offseason) setOff(body.offseason);
      if (body.game) ctx.setGame(body.game);
      ctx.bump();
    },
    [ctx],
  );

  async function run(kind: Exclude<Busy, null>, fn: () => Promise<SimOffseasonResponse>, message?: (body: SimOffseasonResponse) => string) {
    setBusy(kind);
    const body = await call(fn);
    setBusy(null);
    if (body) {
      apply(body);
      const text = message?.(body);
      if (text) ctx.notify(text, "success");
    }
  }

  if (state === "loading" && !off) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <SkeletonCard lines={3} />
        <SkeletonCard lines={5} />
      </div>
    );
  }
  if (state === "error" || !off) {
    return <EmptyState title="Could not load the offseason" subtitle="Check your connection and try again." actionLabel="Try again" onAction={() => { setState("loading"); setAttempt((n) => n + 1); }} />;
  }

  const cta = simOffseasonCta(off);
  const steps = simOffseasonSteps(off.stage);

  return (
    <div className="flex flex-col gap-3" data-testid="offseason">
      <AccentCard accent="var(--color-accent)" compact as="section">
        <p className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {simOffseasonHeading(off)}
        </p>
        <ol className="flex flex-wrap items-center gap-2" aria-label="Offseason steps">
          {steps.map((step) => (
            <li key={step.key} aria-current={step.state === "current" ? "step" : undefined}>
              <SimToneBadge label={step.label} tone={step.state === "current" ? "accent" : step.state === "done" ? "success" : "muted"} />
            </li>
          ))}
        </ol>
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {simOffseasonProgressLine(off)}
        </p>
      </AccentCard>

      {years.length > 0 && off.stage === "review" ? <SimDynastyStrip years={years} /> : null}

      {off.stage === "review" ? <ReviewStage off={off} ctx={ctx} years={years} /> : null}
      {off.stage === "rookie_draft" ? (
        <RookieStage
          off={off}
          ctx={ctx}
          pos={pos}
          setPos={setPos}
          busy={busy}
          onPick={(player) => run("pick", () => api.pickSimRookie(gameId, player.id), (b) => `Drafted ${player.name}.${(b.made?.length ?? 0) > 1 ? " The AI picks ran up to your next turn." : ""}`)}
        />
      ) : null}
      {off.stage === "cutdown" ? <CutdownStage off={off} ctx={ctx} onTrade={onTrade} onTeam={onTeam} /> : null}

      <div className="sticky bottom-16 flex flex-col gap-2 md:bottom-2">
        {off.stage === "rookie_draft" && confirmAuto ? (
          <AccentCard accent="var(--color-warning)" compact as="div">
            <p className="text-sm" role="alert">Auto-draft makes every one of your remaining picks for you, best available by your needs.</p>
            <div className="flex gap-2">
              <Button size="sm" loading={busy === "auto"} onClick={() => { setConfirmAuto(false); void run("auto", () => api.autoSimRookieDraft(gameId), () => "The rookie draft is done."); }}>
                Auto-draft the rest
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setConfirmAuto(false)}>Keep drafting</Button>
            </div>
          </AccentCard>
        ) : null}
        {cta.blocked ? (
          <p className="text-xs font-semibold" role="status" style={{ color: "var(--color-warning)" }}>{cta.blocked}</p>
        ) : null}
        {off.stage === "review" ? (
          <Button fullWidth loading={busy === "start"} onClick={() => void run("start", () => api.startSimRookieDraft(gameId), (b) => ((b.made?.length ?? 0) > 0 ? `${b.made?.length} AI picks made. You are up.` : ""))}>
            {cta.label}
          </Button>
        ) : null}
        {off.stage === "rookie_draft" ? (
          <Button fullWidth variant="secondary" loading={busy === "auto"} disabled={busy === "pick" || confirmAuto} onClick={() => setConfirmAuto(true)}>
            {cta.label}
          </Button>
        ) : null}
        {off.stage === "cutdown" ? (
          <Button fullWidth loading={busy === "season"} disabled={Boolean(cta.blocked)} onClick={() => void run("season", async () => (await api.startSimSeason(gameId)) as SimOffseasonResponse, () => `Season ${off.season_no + 1} is on.`)}>
            {cta.label}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Review

function ReviewStage({ off, ctx, years }: { off: SimOffseason; ctx: SimCtx; years: SimDynastyYear[] }) {
  const last = off.last_season;
  const lastYear = last ? simArchiveToYear(last) : null;
  const retired = simRetireesSorted(off.retired);
  const yours = retired.filter((r) => r.is_yours);
  const movers = off.movers ?? [];
  const rose = movers.filter((m) => m.delta >= 0.5).length;
  const fell = movers.filter((m) => m.delta <= -0.5).length;
  const mine = off.your_picks_this_draft ?? [];
  const titles = ctx.game.dynasty?.titles ?? years.filter((y) => y.champion?.is_you).length;
  const classChip = simRookieClassChip(off);
  const [notice, setNotice] = useState(false);
  return (
    <>
      {notice ? <SimGeneratedNoticeSheet onClose={() => setNotice(false)} /> : null}
      {last && lastYear ? (
        <SimCollapse
          title={`${last.year} season`}
          summary={`${lastYear.record}, ${simOrdinal(lastYear.rank)} · ${simPlayoffResultLabel(lastYear.playoff_result)}`}
          tone={last.champion?.is_you ? "success" : "accent"}
          defaultOpen
          testId="off-last-season"
        >
          <div className="flex flex-wrap items-center gap-2">
            <SimToneBadge label={simPlayoffResultLabel(lastYear.playoff_result)} tone={simPlayoffOutcomeTone(lastYear.playoff_result)} size="sm" />
            <span className="text-sm font-bold tabular-nums">{lastYear.record}</span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{simFmtPts(lastYear.pf)} PF</span>
          </div>
          <p className="text-xs" style={{ color: last.champion?.is_you ? "var(--color-success)" : "var(--color-text-muted)" }}>
            Champion: {last.champion ? `${last.champion.name}${last.champion.is_you ? " (you)" : ""}` : "none"}
            {titles > 0 ? ` · ${titles} title${titles === 1 ? "" : "s"} so far` : ""}
          </p>
          {lastYear.top_scorers.length > 0 ? (
            <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              Top scorers: {lastYear.top_scorers.map((s) => `${s.name} ${s.pts.toFixed(1)}`).join(", ")}
            </p>
          ) : null}
        </SimCollapse>
      ) : null}

      <SimCollapse
        title="Retirements"
        summary={retired.length === 0 ? "Nobody retired" : `${retired.length} retired${yours.length ? `, ${yours.length} yours` : ""}`}
        tone={yours.length ? "danger" : "muted"}
        defaultOpen={yours.length > 0}
        testId="off-retired"
      >
        {retired.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No notable retirements this year.</p>
        ) : (
          <ul className="flex flex-col">
            {retired.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-2 py-2" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
                <span className="flex min-w-0 flex-col leading-tight">
                  <span className="text-sm font-bold">{r.name}</span>
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{r.pos}{r.age != null ? ` · age ${r.age}` : ""}</span>
                </span>
                {r.is_yours ? <SimToneBadge label="Yours" tone="danger" /> : null}
              </li>
            ))}
          </ul>
        )}
      </SimCollapse>

      <SimCollapse
        title="Aging report"
        summary={movers.length === 0 ? "No change to report" : `${rose} up, ${fell} down on your roster`}
        defaultOpen={movers.length > 0}
        testId="off-aging"
      >
        {movers.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Your roster held steady.</p>
        ) : (
          <>
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Change in expected points per game, last season to this one.</p>
            {movers.map((m) => {
              const t = simMoverText(m);
              return (
                <SimPlayerLine
                  key={m.id}
                  player={m}
                  onOpen={ctx.openPlayer}
                  trailing={
                    <span className="flex flex-col items-end leading-tight" data-testid="mover">
                      <span className="text-sm font-extrabold tabular-nums" style={{ color: simToneColor(t.tone) }}>
                        <span aria-hidden="true">{t.arrow}</span> {t.delta}
                      </span>
                      {t.age ? <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Age {t.age}</span> : null}
                    </span>
                  }
                />
              );
            })}
          </>
        )}
      </SimCollapse>

      {classChip ? (
        <div className="flex flex-wrap items-center gap-x-2" data-testid="review-class">
          <SimGeneratedChip label={classChip} onInfo={() => setNotice(true)} />
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Preview of the incoming class.</span>
        </div>
      ) : null}

      <SimCollapse
        title="Your rookie picks"
        summary={mine.length === 0 ? "You hold no picks this year" : `${mine.length} pick${mine.length === 1 ? "" : "s"} in a ${off.draft.round_count}-round draft`}
        defaultOpen={mine.length > 0}
        testId="off-picks"
      >
        {mine.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>You traded them all away. You can still trade for picks before the draft starts.</p>
        ) : (
          <ul className="flex flex-col">
            {mine.map((row) => (
              <li key={row.pick} className="flex items-center justify-between gap-2 py-2" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
                <span className="text-sm font-bold">{simRookiePickLine(row)}</span>
                {row.traded ? <SimToneBadge label="Traded for" tone="accent" /> : null}
              </li>
            ))}
          </ul>
        )}
      </SimCollapse>
    </>
  );
}

// ---------------------------------------------------------------------------
// Rookie draft

function RookieStage({
  off,
  ctx,
  pos,
  setPos,
  busy,
  onPick,
}: {
  off: SimOffseason;
  ctx: SimCtx;
  pos: SimPos | "";
  setPos: (pos: SimPos | "") => void;
  busy: Busy;
  onPick: (player: SimGamePlayer) => void;
}) {
  const d = off.draft;
  const positions = simPositionsFor(ctx.game.settings.slots);
  const mine = off.your_picks_this_draft ?? [];
  const made = d.order.filter((o) => o.made);
  const classChip = simRookieClassChip(off);
  const [notice, setNotice] = useState(false);
  return (
    <>
      {classChip ? <SimRookieNoticeGate gameId={ctx.gameId} /> : null}
      {notice ? <SimGeneratedNoticeSheet onClose={() => setNotice(false)} /> : null}
      <AccentCard accent={d.your_turn ? "var(--color-action)" : "var(--color-accent)"} compact as="section" glow={d.your_turn}>
        <p className="text-sm font-bold" role="status" data-testid="rookie-clock">{simRookieClockLine(d)}</p>
        {classChip ? <div><SimGeneratedChip label={classChip} onInfo={() => setNotice(true)} /></div> : null}
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {d.available_count} rookie{d.available_count === 1 ? "" : "s"} left. {mine.filter((m) => !m.made).length} pick{mine.filter((m) => !m.made).length === 1 ? "" : "s"} still to make.
        </p>
      </AccentCard>

      <SimCollapse title="Your picks" summary={`${mine.filter((m) => m.made).length} of ${mine.length} made`} defaultOpen testId="rookie-mine">
        {mine.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>You have no picks in this draft.</p>
        ) : (
          <ul className="flex flex-col">
            {mine.map((row) => (
              <li key={row.pick} className="flex items-center justify-between gap-2 py-2" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
                <span className="text-sm font-bold">{simRookiePickLine(row)}</span>
                {row.made ? <SimToneBadge label={row.made.pos} tone="success" /> : d.on_clock?.pick === row.pick ? <SimToneBadge label="On the clock" tone="accent" /> : null}
              </li>
            ))}
          </ul>
        )}
      </SimCollapse>

      <section className="flex flex-col gap-2" aria-label="Available rookies">
        <PillRow
          ariaLabel="Position filter"
          variant="scroll"
          options={[{ label: "All", value: "" }, ...positions.map((p) => ({ label: p, value: p }))]}
          active={pos}
          onSelect={(value) => setPos(value as SimPos | "")}
        />
        {d.available.length === 0 ? (
          <EmptyState title="No rookies left that match" subtitle="Try a different position." />
        ) : (
          <div className="flex flex-col">
            <p className="pb-1 text-xs" style={{ color: "var(--color-text-muted)" }}>Under each name: projection, value and ADP.</p>
            {d.available.map((player) => (
              <SimDraftRow
                key={player.id}
                player={player}
                // Rookie ADP is not comparable to a pick number in this small class, so no steal/reach edge.
                pickNo={player.adp ?? 0}
                onOpen={ctx.openPlayer}
                onGeneratedInfo={() => setNotice(true)}
                actions={
                  d.your_turn ? (
                    <Button size="sm" loading={busy === "pick"} disabled={busy !== null && busy !== "pick"} aria-label={`Draft ${player.name}`} onClick={() => onPick(player)}>
                      Draft
                    </Button>
                  ) : null
                }
              />
            ))}
          </div>
        )}
      </section>

      <SimCollapse title="Draft log" summary={`${made.length} of ${d.total} picks made`} testId="rookie-log">
        {made.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>No picks yet.</p>
        ) : (
          <ol className="flex flex-col">
            {[...made].reverse().slice(0, 30).map((row) => (
              <li key={row.pick} className="flex items-center justify-between gap-2 py-1.5 text-xs" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
                <span className="min-w-0">
                  <span className="font-bold tabular-nums">#{row.n}</span> {row.made?.name} <span style={{ color: "var(--color-text-muted)" }}>({row.made?.pos})</span>
                </span>
                <span className="shrink-0" style={{ color: row.is_yours ? "var(--color-accent)" : "var(--color-text-muted)" }}>{row.is_yours ? "You" : row.team_name}</span>
              </li>
            ))}
          </ol>
        )}
      </SimCollapse>
    </>
  );
}

// ---------------------------------------------------------------------------
// Roster check

function CutdownStage({ off, ctx, onTrade, onTeam }: { off: SimOffseason; ctx: SimCtx; onTrade: () => void; onTeam: () => void }) {
  const { gameId, game, call } = ctx;
  const teamId = game.you?.team_id;
  const [roster, setRoster] = useState<SimTeamRosterResponse | null>(null);
  const [cutting, setCutting] = useState<string | null>(null);
  const [moving, setMoving] = useState<SimGamePlayer | null>(null);
  const picks = useSimPicks(ctx);
  const r = off.roster;

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    api
      .getSimGameTeam(gameId, teamId)
      .then((body) => {
        if (!cancelled && !body.reason) setRoster(body);
      })
      .catch(() => {
        /* the summary above still works */
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, teamId, ctx.tick]);

  async function cut(player: SimGamePlayer) {
    setCutting(null);
    const body = await call(() => api.cutSimPlayer(gameId, player.id));
    if (body) {
      ctx.notify(`Cut ${player.name}.`, "success");
      ctx.bump();
      await ctx.reloadGame();
    }
  }

  const over = r.cuts_needed > 0;
  const players = roster?.players ?? [];
  const reservesOn = simReservesOn(game.settings, roster?.reserves ?? r.reserves);
  const reserveState = { reserves: roster?.reserves ?? r.reserves, rosterSize: r.size, rosterLimit: r.limit };
  const myPicks = simPicksOf(picks, teamId);
  return (
    <>
      <AccentCard accent={over ? "var(--color-danger)" : "var(--color-success)"} compact as="section">
        <p className="text-sm font-bold" role={over ? "alert" : "status"} data-testid="roster-check">
          {over ? `Cut ${r.cuts_needed} player${r.cuts_needed === 1 ? "" : "s"} to start the season.` : "Your roster is ready for the season."}
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {r.size} of {r.limit} roster spots. IR and taxi players do not count.
        </p>
        <div className="flex flex-wrap gap-2 pt-1">
          {off.can_trade ? <Button size="sm" variant="secondary" onClick={onTrade}>Shop a trade</Button> : null}
          <Button size="sm" variant="ghost" onClick={onTeam}>Open Team tab</Button>
        </div>
      </AccentCard>

      <SimCollapse title="Your roster" summary={`${r.size} of ${r.limit}${over ? `, cut ${r.cuts_needed}` : ""}`} tone={over ? "danger" : "muted"} defaultOpen={over} testId="cutdown-roster">
        {players.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Loading your roster.</p>
        ) : (
          players.map((player) => (
            <SimPlayerLine
              key={player.id}
              player={player}
              onOpen={ctx.openPlayer}
              extra={<SimPlayerChips player={player} />}
              trailing={
                cutting === player.id ? (
                  <>
                    <Button size="sm" variant="danger" onClick={() => void cut(player)}>Cut {player.name.split(" ").slice(-1)[0]}</Button>
                    <Button size="sm" variant="ghost" onClick={() => setCutting(null)}>Keep</Button>
                  </>
                ) : (
                  <>
                    <SimStat label="Value" value={Math.round(player.value)} />
                    {reservesOn ? <SimReserveButton player={player} onOpen={setMoving} /> : null}
                    <Button size="sm" variant={over ? "dangerOutline" : "ghost"} aria-label={`Cut ${player.name}`} onClick={() => setCutting(player.id)}>
                      Cut
                    </Button>
                  </>
                )
              }
            />
          ))
        )}
      </SimCollapse>

      {reservesOn ? (
        <SimReserveGroups ir={roster?.ir ?? r.ir ?? []} taxi={roster?.taxi ?? r.taxi ?? []} state={reserveState} onOpen={setMoving} openPlayer={ctx.openPlayer} />
      ) : null}

      {game.settings.mode === "dynasty" && myPicks.length > 0 ? (
        <SimCollapse title="Your future picks" summary={`${myPicks.length} pick${myPicks.length === 1 ? "" : "s"}`} testId="cutdown-picks">
          {myPicks.map((pick) => (
            <SimPickLine key={pick.id} pick={pick} draftYear={picks?.draft_year} />
          ))}
        </SimCollapse>
      ) : null}

      {moving ? (
        <SimReserveSheet
          ctx={ctx}
          player={moving}
          state={reserveState}
          onClose={() => setMoving(null)}
          onMoved={(_, player, to) => {
            setMoving(null);
            ctx.notify(`${player.name} ${to === "ir" ? "is on IR" : to === "taxi" ? "is on the taxi squad" : "is back on your roster"}.`, "success");
            ctx.bump();
          }}
        />
      ) : null}
    </>
  );
}

