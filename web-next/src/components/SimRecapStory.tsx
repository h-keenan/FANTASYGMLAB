"use client";

import { useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/Button";
import { SimPlayerChip, SimPlayerLine, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { SimWeekRecapView } from "@/components/SimGameRecap";
import { StoryCarousel, type StoryPage } from "@/components/ui/StoryCarousel";
import { simFmtPts, simPlayoffRoundLabel, simResultLabel, simResultTone, simTeamNameMap, type SimWeekRecap } from "@/lib/simGame";
import {
  simLeagueHighlights,
  simNextWeekModel,
  simPositionTotals,
  simRecapInjuryModel,
  simRecapPageKeys,
  simRecapProj,
  simRecapResultModel,
  simTopStarters,
  type SimRecapFacts,
  type SimRecapPageKey,
} from "@/lib/simRecapStory";

const KICKER: Record<SimRecapPageKey, string> = {
  result: "Result",
  matchup: "Matchup breakdown",
  injuries: "Injuries and lineup",
  league: "Around the league",
  next: "Next week",
};

function Hero({ value, caption, color }: { value: ReactNode; caption?: string; color?: string }) {
  return (
    <div className="flex flex-col items-center gap-1 text-center">
      <span className="text-5xl font-extrabold tabular-nums leading-none" style={{ color: color ?? "var(--color-text-primary)" }}>{value}</span>
      {caption ? <span className="text-sm font-semibold" style={{ color: "var(--color-text-secondary)" }}>{caption}</span> : null}
    </div>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl px-3 py-2" style={{ background: "var(--glass-input-bg)" }}>
      <span className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{label}</span>
      <span className="min-w-0 text-right text-sm font-bold">{children}</span>
    </div>
  );
}

export function recapFacts(recap: SimWeekRecap, ctx: SimCtx): SimRecapFacts {
  const g = ctx.game;
  const names = simTeamNameMap([...(recap.standings ?? []).map((r) => ({ team_id: r.team_id, name: r.name })), ...(g.you ? [{ team_id: g.you.team_id, name: g.you.name }] : [])]);
  const tw = g.this_week;
  return {
    youId: g.you?.team_id ?? null,
    names,
    lineupWarnings: g.pending?.lineup_warnings ?? 0,
    offers: g.pending?.inbox ?? 0,
    nextOpponent: tw?.opponent?.name ?? null,
    nextProjection: tw && !tw.bye ? { yours: tw.your_projection, theirs: tw.opponent_projection } : null,
    tradeDeadlineWeek: g.trade_deadline_week,
    week: g.week,
  };
}

/** The weekly recap as a story: Result, Matchup, Injuries and lineup, Around the league, Next week. */
export function SimWeekRecapStory({
  recap,
  index,
  total,
  ctx,
  onNext,
  onClose,
  onFixLineup,
}: {
  recap: SimWeekRecap;
  index: number;
  total: number;
  ctx: SimCtx;
  onNext: () => void;
  onClose: () => void;
  onFixLineup: () => void;
}) {
  const [detail, setDetail] = useState(false);
  const facts = useMemo(() => recapFacts(recap, ctx), [recap, ctx]);
  const keys = useMemo(() => simRecapPageKeys(recap, facts), [recap, facts]);
  const last = index + 1 >= total;
  const title = recap.kind === "playoff" ? `${simPlayoffRoundLabel(recap.week, ctx.game.settings)} recap` : `Week ${recap.week} recap`;

  if (detail) return <SimWeekRecapView recap={recap} index={index} total={total} ctx={ctx} onNext={onNext} onClose={onClose} />;

  const finishLabel = !last ? "Next round" : recap.season_complete ? (ctx.game.status === "offseason" ? "Go to the offseason" : ctx.game.settings.mode === "dynasty" ? "See your dynasty review" : "See your final grade") : "Back to your team";
  const finish = (
    <>
      <Button fullWidth onClick={last ? onClose : onNext}>{finishLabel}</Button>
      <Button fullWidth variant="ghost" onClick={() => setDetail(true)}>Full details</Button>
    </>
  );

  const result = simRecapResultModel(recap);
  const game = recap.your_game;
  const tone = simResultTone(game?.result);
  const pageFor = (key: SimRecapPageKey): ReactNode => {
    if (key === "result") {
      return result.kind === "bye" ? (
        <Hero value="Bye" caption="You had a bye this week." />
      ) : (
        <>
          <div className="flex items-center justify-center gap-2">
            <SimToneBadge label={simResultLabel(game?.result)} tone={tone} size="sm" />
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>vs {result.opponent}</span>
          </div>
          <div className="flex items-baseline justify-center gap-3" aria-label={`You ${simFmtPts(result.yours)}, ${result.opponent} ${simFmtPts(result.theirs)}`}>
            <span className="text-6xl font-extrabold tabular-nums leading-none" style={{ color: simToneColor(tone) }}>{simFmtPts(result.yours)}</span>
            <span style={{ color: "var(--color-text-muted)" }}>to</span>
            <span className="text-4xl font-bold tabular-nums" style={{ color: "var(--color-text-secondary)" }}>{simFmtPts(result.theirs)}</span>
          </div>
          <p className="text-center text-base font-bold">{result.margin}</p>
          <div className="flex flex-col gap-2">
            {result.best ? <Fact label="Best performer">{result.best.name} · {simFmtPts(result.best.pts)}</Fact> : null}
            {result.worst ? <Fact label="Worst performer">{result.worst.name} · {simFmtPts(result.worst.pts)}</Fact> : null}
          </div>
        </>
      );
    }
    if (key === "matchup" && game) {
      const totals = simPositionTotals(game.starters);
      return (
        <>
          <Hero value={game.efficiency != null ? `${Math.round(game.efficiency * 100)}%` : simFmtPts(game.your_pts)} caption={game.optimal_pts != null ? `Lineup efficiency. Best possible: ${simFmtPts(game.optimal_pts)}` : "Your lineup"} color="var(--color-accent)" />
          <ul className="flex flex-wrap justify-center gap-2" aria-label="Points by position">
            {totals.map((t) => (
              <li key={t.pos} className="rounded-full px-2.5 py-1 text-xs font-bold tabular-nums" style={{ background: "var(--glass-input-bg)" }}>
                <span style={{ color: "var(--color-text-muted)" }}>{t.pos}</span> {simFmtPts(t.pts)}
              </li>
            ))}
          </ul>
          <div className="flex flex-col">
            {simTopStarters(game.starters).map((s, i) => (
              <SimPlayerLine key={`${s.slot}-${i}`} player={s.player!} stats={[{ key: "pts", label: "Pts", value: simFmtPts(s.pts), tone: simRecapProj(s) != null && s.pts >= simRecapProj(s)! ? "success" : undefined }, { key: "proj", label: "Proj", value: simFmtPts(simRecapProj(s)) }]} onOpen={ctx.openPlayer} />
            ))}
          </div>
        </>
      );
    }
    if (key === "injuries") {
      const m = simRecapInjuryModel(recap);
      const hero = m.yours > 0 ? `${m.yours}` : m.items.length > 0 ? `${m.items.length} hurt` : `${facts.lineupWarnings}`;
      return (
        <>
          <Hero value={hero} caption={m.yours > 0 ? "of your players got hurt" : m.items.length > 0 ? "injuries around the league" : "lineup issues to fix"} color={m.yours > 0 || facts.lineupWarnings > 0 ? "var(--color-danger)" : undefined} />
          <ul className="flex flex-col gap-2">
            {m.items.map((inj, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <SimPlayerChip player={{ ...inj.player, status: "out", out_weeks: inj.weeks }} onOpen={ctx.openPlayer} />
                <span className="shrink-0 text-xs font-bold" style={{ color: "var(--color-danger)" }}>Out {inj.weeks}w{inj.is_yours ? " · yours" : ""}</span>
              </li>
            ))}
          </ul>
          {m.zeroStarters.length > 0 ? <p className="text-center text-sm" style={{ color: "var(--color-warning)" }}>{m.zeroStarters.map((z) => `${z.name} (${z.flag})`).slice(0, 3).join(", ")} scored 0.</p> : null}
          {facts.lineupWarnings > 0 ? <p className="text-center text-sm font-semibold" style={{ color: "var(--color-warning)" }}>{facts.lineupWarnings} lineup issue{facts.lineupWarnings === 1 ? "" : "s"} for next week.</p> : null}
        </>
      );
    }
    if (key === "league") {
      const h = simLeagueHighlights(recap, facts.names);
      return (
        <>
          <Hero value={h.hero?.value ?? ""} caption={h.hero?.who ? `Top score: ${h.hero.who}` : undefined} color="var(--color-success)" />
          <div className="flex flex-col gap-2">
            {h.items.map((it) => (
              <Fact key={it.key} label={it.label}>{it.detail}</Fact>
            ))}
          </div>
        </>
      );
    }
    if (key === "next") {
      const n = simNextWeekModel(recap, facts);
      return (
        <>
          <Hero value={n.opponent ?? `Week ${n.week ?? ""}`} caption={n.week != null ? `Week ${n.week}${n.opponent ? " opponent" : ""}` : undefined} />
          {n.yours != null && n.theirs != null ? (
            <p className="text-center text-lg font-bold tabular-nums">
              <span style={{ color: "var(--color-accent)" }}>{simFmtPts(n.yours)}</span> <span style={{ color: "var(--color-text-muted)" }}>proj vs</span> {simFmtPts(n.theirs)}
            </p>
          ) : null}
          {n.edge ? <p className="text-center text-sm font-semibold" style={{ color: "var(--color-text-secondary)" }}>{n.edge}</p> : null}
          <div className="flex flex-col gap-2">
            {n.notes.map((note) => (
              <Fact key={note.label} label={note.label}>{note.text}</Fact>
            ))}
          </div>
        </>
      );
    }
    return null;
  };

  const pages: StoryPage[] = keys.map((key, i) => ({
    key,
    label: `${title}${total > 1 ? ` · ${index + 1} of ${total}` : ""} · ${KICKER[key]}`,
    content: pageFor(key),
    footer:
      i === keys.length - 1 ? (
        <>
          {key === "injuries" ? <Button fullWidth variant="secondary" onClick={onFixLineup}>Fix lineup</Button> : null}
          {finish}
        </>
      ) : key === "injuries" ? (
        <Button fullWidth variant="secondary" onClick={onFixLineup}>Fix lineup</Button>
      ) : undefined,
  }));
  return <StoryCarousel key={`${recap.week}-${recap.kind}`} title={title} pages={pages} onClose={last ? onClose : onNext} testId="week-recap-story" />;
}
