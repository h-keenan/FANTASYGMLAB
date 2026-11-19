"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button, ButtonLink } from "@/components/Button";
import { PillRow } from "@/components/PillRow";
import { SeasonWrapped } from "@/components/SeasonWrapped";
import { SectionHeading } from "@/components/SectionHeading";
import { SimPlayerChip, SimToneBadge, type SimCtx } from "@/components/SimGameParts";
import { SkeletonCard } from "@/components/Skeleton";
import { Collapse } from "@/components/ui/Presence";
import { api } from "@/lib/api";
import type { SimGameCreateBody, SimPos } from "@/lib/simGame";
import {
  SIM_WATCH_TRADE_OPTIONS,
  SIM_WATCH_WAIVER_OPTIONS,
  normalizeWatchReport,
  simWatchGradeMove,
  simWatchMoves,
  simWatchOutcomeText,
  simWatchPlaybackLine,
  simWatchRerunBody,
  simWatchSliders,
  simWatchTradeLabel,
  simWatchWaiverLabel,
  type SimWatchLine,
  type SimWatchPlayer,
  type SimWatchReport,
  type SimWatchWhatIf,
} from "@/lib/simWatch";
import { normalizeWrappedDeck, type WrappedDeck } from "@/lib/wrapped";

const MAX_WEEKS = 40;
const SPEEDS = [
  { label: "1X", value: "1", pause: 650 },
  { label: "2X", value: "2", pause: 325 },
  { label: "Skip to end", value: "end", pause: 0 },
];

/** The report's player brief as a sim player ref (the server sends the position as a plain string). */
const ref = (p: SimWatchPlayer) => ({ ...p, pos: p.pos as SimPos });

const eyebrow = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" } as const;

/** The Draft & Watch settings (setup): lineups are always on, then a waiver slider and a trade slider, three options each so tabs. */
export function SimWatchSliders({ waivers, trades, onWaivers, onTrades }: { waivers: string; trades: string; onWaivers: (value: string) => void; onTrades: (value: string) => void }) {
  const waiverNote = SIM_WATCH_WAIVER_OPTIONS.find((o) => o.value === waivers)?.note;
  const tradeNote = SIM_WATCH_TRADE_OPTIONS.find((o) => o.value === trades)?.note;
  return (
    <div className="flex flex-col gap-3" data-testid="watch-sliders">
      <div className="glass-surface flex flex-col gap-1 p-4">
        <div className="flex items-start justify-between gap-2">
          <span className="text-base font-extrabold">Lineups</span>
          <SimToneBadge label="Always on" tone="success" />
        </div>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>Best projected lineup every week.</p>
      </div>
      <div className="glass-surface flex flex-col gap-2 p-4">
        <span className="text-base font-extrabold">Waiver activity</span>
        <PillRow ariaLabel="Waivers" variant="fill" options={SIM_WATCH_WAIVER_OPTIONS.map((o) => ({ label: o.label, value: o.value }))} active={waivers} onSelect={onWaivers} />
        {waiverNote ? <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{waiverNote}</p> : null}
        <span className="self-start"><SimToneBadge label="Need-based" tone="accent" /></span>
      </div>
      <div className="glass-surface flex flex-col gap-2 p-4">
        <span className="text-base font-extrabold">Trade activity</span>
        <PillRow ariaLabel="Trades" variant="fill" options={SIM_WATCH_TRADE_OPTIONS.map((o) => ({ label: o.label, value: o.value }))} active={trades} onSelect={onTrades} />
        {tradeNote ? <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{tradeNote}</p> : null}
      </div>
    </div>
  );
}

function ResultDot({ result }: { result: SimWatchLine["result"] }) {
  const win = result === "W";
  return (
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-extrabold" style={{ border: `1px solid ${win ? "var(--color-success)" : "var(--color-border-strong)"}`, color: win ? "var(--color-success)" : "var(--color-text-secondary)" }}>
      {result || "-"}
    </span>
  );
}

/** After the draft: one button plays the season back week by week (1X, 2X or straight to the end). */
export function SimWatchPlayback({ ctx }: { ctx: SimCtx }) {
  const sliders = simWatchSliders(ctx.game.settings);
  const [lines, setLines] = useState<SimWatchLine[]>([]);
  const [moves, setMoves] = useState<{ title: string; sub: string }[]>([]);
  const [running, setRunning] = useState(false);
  const [latestYou, setLatestYou] = useState<SimCtx['game']['you'] | null>(null);
  const [speed, setSpeed] = useState("1");
  const speedRef = useRef("1");
  const paused = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function play() {
    paused.current = false;
    setRunning(true);
    let game = ctx.game;
    for (let i = 0; i < MAX_WEEKS && !paused.current; i += 1) {
      const res = await ctx.call(() => api.advanceSimGame(game.id, game.week));
      if (!res?.recap || !res.game) break;
      const recaps = [res.recap, ...(res.also_played ?? [])];
      const added = recaps.map(simWatchPlaybackLine).filter((l): l is SimWatchLine => l !== null);
      const made = recaps.flatMap((r) => simWatchMoves(r, res.game?.you?.team_id ?? ctx.game.you?.team_id));
      if (mounted.current) {
        setLines((prev) => [...prev, ...added]);
        if (made.length) setMoves((prev) => [...prev, ...made].slice(-6));
      }
      game = res.game;
      if (mounted.current && res.game.you) setLatestYou(res.game.you);
      ctx.setGame(res.game);
      if (res.game.status === "complete" || res.game.status === "offseason") break;
      const pause = SPEEDS.find((sp) => sp.value === speedRef.current)?.pause ?? 650;
      if (pause > 0) await new Promise((resolve) => setTimeout(resolve, pause));
    }
    if (mounted.current) setRunning(false);
  }

  // The record comes from the same answer as each results row (the game the advance call returned), not from a re-render that may lag it.
  const you = latestYou ?? ctx.game.you;
  const total = ctx.game.settings.regular_weeks || 14;
  const started = lines.length > 0;
  const record = you ? `${you.wins}-${you.losses}${you.ties ? `-${you.ties}` : ""}` : "0-0";
  const weeksPlayed = Math.min(total, lines.length);
  return (
    <section className="flex flex-col gap-3" aria-label="Draft and Watch" data-testid="watch-playback">
      <p className="text-xs font-extrabold uppercase" style={eyebrow}>{started ? "Watching the season" : "Draft & Watch"}</p>
      <h2 className="text-2xl font-extrabold">{started ? `Week ${Math.min(total, weeksPlayed + (running ? 1 : 0))} of ${total}` : "Your draft is in"}</h2>
      <div className="glass-surface flex flex-col items-center gap-3 p-4">
        <span className="text-xs font-extrabold uppercase" style={eyebrow}>Record</span>
        <span className="text-5xl font-extrabold tabular-nums" data-testid="watch-record">{record}</span>
        <div className="h-2 w-full rounded-full" style={{ background: "var(--color-surface-muted)" }}><div className="h-2 rounded-full" style={{ width: `${(weeksPlayed / total) * 100}%`, background: "var(--color-accent)" }} /></div>
        <PillRow ariaLabel="Playback speed" variant="fill" options={SPEEDS.map((sp) => ({ label: sp.label, value: sp.value }))} active={speed} onSelect={(v) => { speedRef.current = v; setSpeed(v); }} />
        {sliders ? (
          <div className="flex flex-wrap justify-center gap-2">
            <SimToneBadge label={`Waivers: ${simWatchWaiverLabel(sliders.waivers)}`} tone="muted" />
            <SimToneBadge label={`Trades: ${simWatchTradeLabel(sliders.trades)}`} tone="muted" />
          </div>
        ) : null}
      </div>
      {started ? (
        <section className="glass-surface flex flex-col gap-2 p-4" aria-label="Results" aria-live="polite">
          <span className="text-xs font-extrabold uppercase" style={eyebrow}>Results</span>
          <ol className="flex flex-col gap-2">
            {[...lines].reverse().map((l) => (
              <li key={`${l.week}-${l.text}`} className="flex items-center gap-3">
                <ResultDot result={l.result} />
                <span className="min-w-0 flex-1 text-sm font-semibold">{l.label}</span>
                <span className="text-sm tabular-nums" style={{ color: "var(--color-text-secondary)" }}>{l.score}</span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      {moves.length ? (
        <section className="glass-surface flex flex-col gap-2 p-4" aria-label="Moves we made">
          <span className="text-xs font-extrabold uppercase" style={eyebrow}>Moves we made</span>
          <ul className="flex flex-col gap-2">
            {[...moves].reverse().map((m, i) => (
              <li key={i} className="flex flex-col">
                <span className="text-sm font-bold">{m.title}</span>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{m.sub}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {running ? (
        <Button variant="secondary" fullWidth onClick={() => { paused.current = true; }}>Pause</Button>
      ) : (
        <Button fullWidth onClick={() => void play()}>{started ? "Keep going" : "Sim the season"}</Button>
      )}
    </section>
  );
}

function GradeChip({ grade }: { grade: string }) {
  const good = /^[AB]/.test(grade);
  return (
    <span className="inline-flex h-10 min-w-10 items-center justify-center rounded-full px-3 text-lg font-extrabold" style={{ border: `2px solid ${good ? "var(--color-success)" : "var(--color-border-strong)"}`, color: good ? "var(--color-success)" : "var(--color-text-secondary)" }}>
      {grade}
    </span>
  );
}

function WhatIf({ item }: { item: SimWatchWhatIf }) {
  const [open, setOpen] = useState(false);
  return (
    <AccentCard accent="var(--color-accent)" compact as="div">
      <button type="button" className="flex w-full items-center justify-between gap-2 text-left" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="text-sm font-bold">{item.title}</span>
        <SimToneBadge label={`+${item.delta.toFixed(1)} pts`} tone="success" />
      </button>
      <Collapse open={open} className="flex flex-col gap-2 pt-1">
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{item.text}</p>
        {item.players.map((p) => <SimPlayerChip key={p.id} player={ref(p)} size={28} quick />)}
      </Collapse>
    </AccentCard>
  );
}

/** The end of Draft & Watch: the report card story opens by itself; the page behind it keeps the same facts and the next-run actions. */
export function SimWatchReportCard({ ctx, onStartGame, onHub }: { ctx: SimCtx; onStartGame: (body: SimGameCreateBody) => void; onHub: () => void }) {
  const [report, setReport] = useState<SimWatchReport | null>(null);
  const [isPro, setIsPro] = useState(false);
  const [failed, setFailed] = useState(false);
  const [story, setStory] = useState(true);
  useEffect(() => {
    let cancelled = false;
    api
      .getSimWatchReport(ctx.gameId)
      .then((body) => {
        if (cancelled) return;
        const parsed = normalizeWatchReport(body.report);
        if (parsed) {
          setReport(parsed);
          setIsPro(body.is_premium === true);
        } else setFailed(true);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ctx.gameId]);

  const deck: WrappedDeck | null = useMemo(
    () => (report ? normalizeWrappedDeck({ kind: "sim", partial: false, season_label: "Draft & Watch", team_name: ctx.game.you?.name ?? "", cards: report.cards }) : null),
    [report, ctx.game.you?.name],
  );

  if (failed) return <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Your season is saved, but the report card could not load. Try again in a moment.</p>;
  if (!report) return <div className="flex flex-col gap-3" aria-busy="true"><SkeletonCard lines={4} /><SkeletonCard lines={6} /></div>;

  const move = simWatchGradeMove(report.draft.then?.grade, report.draft.now.grade);
  const rerun = (same: boolean) => onStartGame(simWatchRerunBody(ctx.game.settings, same) as SimGameCreateBody);
  const actions = (
    <>
      {isPro ? (
        <>
          <Button fullWidth onClick={() => rerun(true)}>Run it back</Button>
          <p className="text-center text-xs" style={{ color: "var(--color-text-muted)" }}>Same draft, new luck</p>
          <Button fullWidth variant="secondary" onClick={() => rerun(false)}>Draft again</Button>
        </>
      ) : (
        <>
          <ButtonLink href="/premium" variant="premium" fullWidth>Run it back · Pro</ButtonLink>
          <p className="text-center text-xs" style={{ color: "var(--color-text-muted)" }}>Same draft, new luck</p>
          <ButtonLink href="/premium" variant="premiumOutline" fullWidth>Draft again · Pro</ButtonLink>
        </>
      )}
    </>
  );
  return (
    <div className="flex flex-col gap-3" data-testid="watch-report">
      <AccentCard accent="var(--color-accent)" as="section" glow>
        <p className="text-xs uppercase font-extrabold" style={eyebrow}>Draft report card</p>
        <h2 className="text-xl font-extrabold">{simWatchOutcomeText(report.standing.outcome)}</h2>
        <p className="text-sm tabular-nums" style={{ color: "var(--color-text-secondary)" }}>{report.standing.record} · #{report.standing.rank} of {report.standing.teams}</p>
        <div className="flex items-center gap-3" aria-label="Draft grade, then and now">
          {report.draft.then ? (
            <div className="flex flex-col items-center gap-1"><GradeChip grade={report.draft.then.grade} /><span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Draft day</span></div>
          ) : null}
          {report.draft.then ? <span aria-hidden style={{ color: move === "up" ? "var(--color-success)" : "var(--color-text-muted)" }}>{move === "up" ? "↗" : move === "down" ? "↘" : "→"}</span> : null}
          <div className="flex flex-col items-center gap-1"><GradeChip grade={report.draft.now.grade} /><span className="text-xs" style={{ color: "var(--color-text-muted)" }}>After the season</span></div>
        </div>
        {deck ? <Button variant="accentOutline" onClick={() => setStory(true)}>Open your report card</Button> : null}
      </AccentCard>

      {report.best_value?.player ? (
        <section className="flex flex-col gap-1" aria-label="Best value pick">
          <SectionHeading>Best value pick</SectionHeading>
          <AccentCard accent="var(--color-success)" compact as="div">
            <SimPlayerChip player={ref(report.best_value.player)} quick extra={<span className="text-xs tabular-nums" style={{ color: "var(--color-success)" }}>{report.best_value.pick} · +{report.best_value.over_round.toFixed(1)} over his round</span>} />
          </AccentCard>
        </section>
      ) : null}

      {report.bust?.player ? (
        <section className="flex flex-col gap-1" aria-label="Biggest bust">
          <SectionHeading>Biggest bust</SectionHeading>
          <AccentCard accent="var(--color-border-strong)" compact as="div">
            <SimPlayerChip player={ref(report.bust.player)} quick extra={<span className="text-xs tabular-nums" style={{ color: "var(--color-text-muted)" }}>{report.bust.pick} · {report.bust.actual.toFixed(1)} of {report.bust.projected.toFixed(1)} projected</span>} />
            <p className="text-sm font-semibold" data-testid="bust-why">Why: {report.bust.why}</p>
          </AccentCard>
        </section>
      ) : null}

      <section className="flex flex-col gap-1" aria-label="What if">
        <SectionHeading>What if</SectionHeading>
        {report.what_ifs.map((w) => <WhatIf key={w.id} item={w} />)}
      </section>

      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Played on {simWatchWaiverLabel(report.sliders.waivers)} waivers and {simWatchTradeLabel(report.sliders.trades)} trades: {report.moves.waivers} add{report.moves.waivers === 1 ? "" : "s"}, {report.moves.trades} trade{report.moves.trades === 1 ? "" : "s"}.
      </p>

      <div className="flex flex-col gap-2">
        {actions}
        <Button variant="ghost" onClick={onHub}>All games</Button>
      </div>
      {deck && story ? <SeasonWrapped deck={deck} itemId={ctx.gameId} onClose={() => setStory(false)} lastFooter={actions} /> : null}
    </div>
  );
}
