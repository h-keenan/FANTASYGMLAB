"use client";

import { Fragment, useMemo, useState, type CSSProperties, type ReactNode } from "react";

import { Button } from "@/components/Button";
import { CountUp, Confetti, MotionIn } from "@/components/Motion";
import { SimAchievementBadge } from "@/components/SimAchievements";
import { TrophyIcon } from "@/components/TrophyIcon";
import { ValueRing } from "@/components/ValueRing";
import { SimPlayerChip, SimPlayerLine, SimSheet, SimToneBadge, type SimCtx } from "@/components/SimGameParts";
import { SimTeamIdentity, SimTeamLogo } from "@/components/SimTeamIdentity";
import { SimWeekRecapView } from "@/components/SimGameRecap";
import { RecapCard } from "@/components/ui/RecapCard";
import { recapCardModel, recapRowsFromItems } from "@/lib/recapCard";
import { StoryCarousel, type StoryPage } from "@/components/ui/StoryCarousel";
import { positionColorVar } from "@/lib/playerPresentation";
import { simAchievementColor, simAchievementDate, simRecapAchievementModel } from "@/lib/simAchievements";
import { simFmtPts, simPlayoffRoundLabel, simTeamNameMap, type SimGamePlayer, type SimWeekRecap } from "@/lib/simGame";
import { simGradeOf } from "@/lib/simGrade";
import {
  STORY_ITEMS,
  simLeagueHighlights,
  simNextWeekModel,
  simPositionTotals,
  simRecapInjuryModel,
  simMovementText,
  simRecapOutcome,
  simRecapPageKeys,
  simRecapPageTitle,
  simRecapStandingsModel,
  type SimStandingsRow,
  simRecapProj,
  simRecapResultModel,
  simRecapSeasonModel,
  simTopStarters,
  type SimRecapFacts,
  type SimRecapOutcome,
  type SimRecapPageKey,
} from "@/lib/simRecapStory";

const KICKER: Record<SimRecapPageKey, string> = {
  result: "Result",
  achievements: "Achievement unlocked",
  matchup: "Matchup breakdown",
  injuries: "Injuries and lineup",
  league: "Around the league",
  standings: "Standings",
  season: "Season complete",
  next: "Next week",
};

const toneVar = (tone: SimRecapOutcome["tone"]) => `var(--color-${tone})`;

/** A page: the hero zone (fills the top of the screen, centered, with a one-shot accent glow) then the supporting rows. */
function Page({ tone = "accent", children }: { tone?: SimRecapOutcome["tone"]; children: ReactNode }) {
  return (
    <div className="ui-recap" style={{ "--recap-tone": toneVar(tone) } as CSSProperties}>
      {children}
    </div>
  );
}

function HeroZone({ children, glow = true }: { children: ReactNode; glow?: boolean }) {
  return (
    <div className="ui-recap-hero">
      {glow ? <span className="ui-recap-glow" aria-hidden="true" data-testid="recap-glow" /> : null}
      {children}
    </div>
  );
}

function Hero({ value, caption, color }: { value: ReactNode; caption?: string; color?: string }) {
  return (
    <div className="flex flex-col items-center gap-1 text-center">
      <span className="text-6xl font-extrabold tabular-nums leading-none" style={{ color: color ?? "var(--color-text-primary)" }}>{value}</span>
      {caption ? <span className="text-sm font-semibold" style={{ color: "var(--color-text-secondary)" }}>{caption}</span> : null}
    </div>
  );
}

function Fact({ label, children, accent }: { label: string; children: ReactNode; accent?: string }) {
  return (
    <div className="ui-recap-fact" style={accent ? ({ "--accent": accent } as CSSProperties) : undefined}>
      <span className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{label}</span>
      <span className="min-w-0 text-right text-sm font-bold">{children}</span>
    </div>
  );
}

/** A glass ring with the efficiency percentage (the same ValueRing the OVR gauge is made of), filling from 0 on arrival. */
function EfficiencyRing({ efficiency }: { efficiency: number }) {
  const pct = Math.round(efficiency * 100);
  return <ValueRing percent={pct} tint="var(--color-accent)" display={`${pct}%`} ariaLabel={`${pct}% lineup efficiency`} size="lg" />;
}

/** The Grade stat, only when the player carries a letter grade: a chip with a label and no value is never rendered. */
const gradeStat = (player: SimGamePlayer | null | undefined) => {
  const grade = simGradeOf(player);
  return grade ? [{ key: "ovr", label: "Grade", value: "", grade }] : [];
};

/** One standings row: rank (or seed), logo + name, record, PF and the movement since last week. */
function StandingsRow({ row }: { row: SimStandingsRow }) {
  const text = simMovementText(row.delta);
  const tone = row.delta == null || row.delta === 0 ? "var(--color-text-muted)" : row.delta > 0 ? "var(--color-success)" : "var(--color-danger)";
  return (
    <li className="ui-recap-standing" data-status={row.status} data-you={row.isYou ? "true" : undefined} data-testid="recap-standing-row">
      <span className="ui-recap-standing-rank">{row.rank}</span>
      <SimTeamIdentity name={row.name} size="row" isYou={row.isYou} bold={row.isYou} className="min-w-0 flex-1" />
      {row.status === "bubble" ? <SimToneBadge label="Bubble" tone="warning" /> : null}
      <span className="ui-recap-standing-rec">{row.record}<small>{simFmtPts(row.pf)} PF</small></span>
      <span className="ui-recap-standing-move" style={{ color: tone }} aria-label={row.delta == null ? undefined : row.delta === 0 ? "No change" : row.delta > 0 ? `Up ${row.delta}` : `Down ${-row.delta}`}>{text}</span>
    </li>
  );
}

/** Rows in rank order with the playoff cut line drawn after the last seed. */
function StandingsList({ rows, spots }: { rows: SimStandingsRow[]; spots: number }) {
  return (
    <ul className="ui-recap-standings" aria-label="Standings">
      {rows.map((r, i) => (
        <Fragment key={r.teamId}>
          <StandingsRow row={r} />
          {spots > 0 && r.rank === spots && rows[i + 1] ? <li className="ui-recap-cut" role="separator" aria-label="Playoff cut line"><span>Playoff cut</span></li> : null}
        </Fragment>
      ))}
    </ul>
  );
}

const performer = (label: string, p: { name: string; pts: number; player: SimGamePlayer | null }, ctx: SimCtx, accent: string) =>
  p.player ? (
    <MotionIn key={label}>
      <p className="mb-0.5 text-xs font-extrabold uppercase" style={{ color: accent, letterSpacing: "var(--letter-spacing-badge)" }}>{label}</p>
      <SimPlayerLine player={p.player} stats={[{ key: "pts", label: "Pts", value: simFmtPts(p.pts), tone: label === "Best performer" ? "success" : undefined }, ...gradeStat(p.player)]} onOpen={ctx.openPlayer} />
    </MotionIn>
  ) : (
    <Fact key={label} label={label} accent={accent}>{p.name} · {simFmtPts(p.pts)}</Fact>
  );

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
    playoffTeams: g.settings.playoff_teams,
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
  const [fullTable, setFullTable] = useState(false);
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
  const outcome = simRecapOutcome(recap, facts.youId);
  const game = recap.your_game;
  const youName = (facts.youId && facts.names[facts.youId]) || ctx.game.you?.name || "You";
  const posChip = (pos: string, children: ReactNode) => (
    <li key={pos} className="ui-recap-chip" style={{ "--pos": `var(${positionColorVar(pos) ?? "--color-text-secondary"})` } as CSSProperties}>
      {children}
    </li>
  );
  const pageFor = (key: SimRecapPageKey): ReactNode => {
    if (key === "result") {
      const label = outcome.headline;
      return (
        <Page tone={outcome.tone}>
          <HeroZone>
            <Confetti wonTitle={outcome.celebrate} />
            {outcome.trophy ? (
              <span className="ui-recap-trophy enter-pop" data-testid="recap-trophy">
                <TrophyIcon size={outcome.celebrate ? 88 : 64} color={toneVar(outcome.celebrate || outcome.variant === "runner_up" ? "premium" : outcome.tone)} label={outcome.headline} />
              </span>
            ) : null}
            <MotionIn>
              <p className="ui-recap-headline" data-testid="recap-headline">{label}</p>
            </MotionIn>
            {outcome.sub ? <p className="ui-recap-sub">{outcome.sub}</p> : null}
            {result.kind === "game" ? (
              <div className="ui-recap-versus" aria-label={`${youName} ${simFmtPts(result.yours)}, ${result.opponent} ${simFmtPts(result.theirs)}`}>
                <div className="ui-recap-team">
                  <SimTeamIdentity name={youName} size="hero" stacked bold={false} nameClassName="ui-recap-team-name" />
                </div>
                <div className="ui-recap-score">
                  <CountUp value={result.yours} className="text-5xl font-extrabold leading-none" style={{ color: toneVar(outcome.tone) }} />
                  <span style={{ color: "var(--color-text-muted)" }}>-</span>
                  <CountUp value={result.theirs} className="text-3xl font-bold" style={{ color: "var(--color-text-secondary)" }} />
                </div>
                <div className="ui-recap-team">
                  <SimTeamIdentity name={result.opponent} size="hero" stacked bold={false} nameClassName="ui-recap-team-name" />
                </div>
              </div>
            ) : null}
            {result.kind === "game" ? <p className="text-base font-bold">{result.margin}</p> : null}
          </HeroZone>
          {result.kind === "game" ? (
            <div className="ui-recap-rows">
              {result.best ? performer("Best performer", result.best, ctx, "var(--color-success)") : null}
              {result.worst ? performer("Worst performer", result.worst, ctx, "var(--color-danger)") : null}
            </div>
          ) : null}
        </Page>
      );
    }
    if (key === "achievements") {
      const m = simRecapAchievementModel(recap.achievements);
      if (!m) return null;
      const hero = m.items[0];
      return (
        <Page tone={m.tone}>
          <HeroZone>
            <Confetti wonTitle={m.celebrate} />
            {m.trophy ? (
              <span className="ui-recap-trophy enter-pop" data-testid="recap-achievement-trophy">
                <TrophyIcon size={m.celebrate ? 88 : 64} color={toneVar(m.tone)} label={m.headline} />
              </span>
            ) : hero ? (
              <span className="enter-pop"><SimAchievementBadge a={hero} size={64} /></span>
            ) : null}
            <p className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{m.eyebrow}</p>
            <MotionIn>
              <p className="ui-recap-headline" data-testid="recap-achievement-headline">{m.headline}</p>
            </MotionIn>
            {m.sub ? <p className="ui-recap-sub">{m.sub}</p> : null}
          </HeroZone>
          <ul className="ui-recap-rows">
            {m.items.slice(1, 1 + STORY_ITEMS).map((a, i, rows) => (
              <MotionIn key={a.id} as="li" index={i} count={rows.length}>
                <div className="ui-recap-fact" style={{ "--accent": simAchievementColor(a) } as CSSProperties}>
                  <span className="inline-flex min-w-0 items-center gap-2">
                    <SimAchievementBadge a={a} size={28} />
                    <span className="min-w-0 break-words text-sm font-extrabold">{a.name}</span>
                  </span>
                  <span className="shrink-0 text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>{simAchievementDate(a)}</span>
                </div>
              </MotionIn>
            ))}
            {m.banners.slice(0, 2).map((b) => (
              <li key={b.kind}>
                <Fact label={b.headline} accent={simAchievementColor({ rarity: "common", tone: b.tone, unlocked: true })}>{b.sub}</Fact>
              </li>
            ))}
          </ul>
        </Page>
      );
    }
    if (key === "matchup" && game) {
      const totals = simPositionTotals(game.starters);
      const top = simTopStarters(game.starters);
      return (
        <Page>
          <HeroZone>
            {game.efficiency != null ? <EfficiencyRing efficiency={game.efficiency} /> : <Hero value={<CountUp value={game.your_pts} />} color="var(--color-accent)" />}
            <p className="text-sm font-semibold" style={{ color: "var(--color-text-secondary)" }}>
              {game.optimal_pts != null ? `Lineup efficiency. Best possible: ${simFmtPts(game.optimal_pts)}` : "Your lineup"}
            </p>
            <ul className="flex flex-wrap justify-center gap-2" aria-label="Points by position">
              {totals.map((t) => posChip(t.pos, <><span>{t.pos}</span> <b>{simFmtPts(t.pts)}</b></>))}
            </ul>
          </HeroZone>
          <div className="flex flex-col">
            {top.map((s, i) => (
              <MotionIn key={`${s.slot}-${i}`} index={i} count={top.length}>
                <SimPlayerLine
                  player={s.player!}
                  stats={[
                    { key: "pts", label: "Pts", value: simFmtPts(s.pts), tone: simRecapProj(s) != null && s.pts >= simRecapProj(s)! ? "success" : undefined },
                    { key: "proj", label: "Proj", value: simFmtPts(simRecapProj(s)) },
                    ...gradeStat(s.player),
                  ]}
                  onOpen={ctx.openPlayer}
                />
              </MotionIn>
            ))}
          </div>
        </Page>
      );
    }
    if (key === "injuries") {
      const m = simRecapInjuryModel(recap);
      const hero = m.yours > 0 ? `${m.yours}` : m.items.length > 0 ? `${m.items.length} hurt` : `${facts.lineupWarnings}`;
      const bad = m.yours > 0 || facts.lineupWarnings > 0;
      return (
        <Page tone={bad ? "danger" : "accent"}>
          <HeroZone>
            <Hero value={hero} caption={m.yours > 0 ? "of your players got hurt" : m.items.length > 0 ? "injuries around the league" : "lineup issues to fix"} color={bad ? "var(--color-danger)" : undefined} />
          </HeroZone>
          <ul className="ui-recap-rows">
            {m.items.map((inj, i) => (
              <MotionIn key={i} as="li" index={i} count={m.items.length}>
                <div className="ui-recap-fact" style={{ "--accent": inj.is_yours ? "var(--color-danger)" : "var(--color-border-strong)" } as CSSProperties}>
                  {/* ONE marker per player: the chip says OUT, the trailing text only how long. */}
                  <SimPlayerChip player={{ ...inj.player, status: "out", out_weeks: inj.weeks }} onOpen={ctx.openPlayer} />
                  <span className="shrink-0 text-xs font-bold" style={{ color: inj.is_yours ? "var(--color-danger)" : "var(--color-text-secondary)" }}>{inj.detail}</span>
                </div>
              </MotionIn>
            ))}
          </ul>
          {m.zeroStarters.length > 0 ? <p className="text-center text-sm" style={{ color: "var(--color-warning)" }}>{m.zeroStarters.map((z) => `${z.name} (${z.flag})`).slice(0, 3).join(", ")} scored 0.</p> : null}
          {facts.lineupWarnings > 0 ? <p className="text-center text-sm font-semibold" style={{ color: "var(--color-warning)" }}>{facts.lineupWarnings} lineup issue{facts.lineupWarnings === 1 ? "" : "s"} for next week.</p> : null}
        </Page>
      );
    }
    if (key === "league") {
      const h = simLeagueHighlights(recap, facts.names);
      return (
        <Page tone="success">
          <HeroZone>
            <p className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>Top score of the week</p>
            <Hero value={h.hero?.value ? <CountUp value={Number(h.hero.value)} /> : ""} caption={h.hero?.who ? `Top score: ${h.hero.who}` : undefined} color="var(--color-success)" />
            {h.hero?.who ? <SimTeamLogo name={h.hero.who} size="card" label /> : null}
          </HeroZone>
          <RecapCard model={recapCardModel({ kicker: "Around the league", rows: recapRowsFromItems(h.items.map((it) => ({ ...it, tone: it.key === "closest" ? ("warning" as const) : it.key === "blowout" ? ("danger" as const) : undefined }))) })} />
        </Page>
      );
    }
    if (key === "standings") {
      const m = simRecapStandingsModel(recap, facts);
      const you = m.you;
      const moveColor = !you || you.delta == null || you.delta === 0 ? "var(--color-text-muted)" : you.delta > 0 ? "var(--color-success)" : "var(--color-danger)";
      return (
        <Page tone={you && you.seed != null ? "success" : "accent"}>
          <HeroZone>
            <Hero value={you ? <CountUp value={you.rank} /> : ""} caption={m.caption || undefined} color={you && you.seed != null ? "var(--color-success)" : undefined} />
            {you && you.delta != null ? <p className="text-2xl font-extrabold tabular-nums" style={{ color: moveColor }} data-testid="standings-move">{simMovementText(you.delta)}</p> : null}
          </HeroZone>
          <StandingsList rows={m.compact} spots={m.spots} />
          {m.rows.length > m.compact.length ? <Button fullWidth variant="secondary" onClick={() => setFullTable(true)}>Full standings</Button> : null}
          {fullTable ? (
            <SimSheet title="Standings" onClose={() => setFullTable(false)}>
              <StandingsList rows={m.rows} spots={m.spots} />
            </SimSheet>
          ) : null}
        </Page>
      );
    }
    if (key === "season") {
      const m = simRecapSeasonModel(recap, facts);
      return (
        <Page tone={m.youChampion || outcome.variant === "runner_up" ? "premium" : "accent"}>
          <HeroZone>
            <span className="ui-recap-trophy enter-pop"><TrophyIcon size={72} color="var(--color-premium)" /></span>
            <p className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{m.youChampion ? "Your finish" : "Champion"}</p>
            <p className="ui-recap-headline" data-testid="season-headline">{m.youChampion ? "Champions" : m.championName ?? "Season complete"}</p>
            {m.championName && !m.youChampion ? <SimTeamLogo name={m.championName} size="card" label /> : null}
            <p className="ui-recap-sub">{m.youChampion ? `${youName} won it all.` : `You finished ${m.finish}.`}</p>
          </HeroZone>
          <RecapCard model={recapCardModel({ kicker: "Season complete", badge: m.finish, rows: recapRowsFromItems(m.items) })} />
        </Page>
      );
    }
    if (key === "next") {
      const n = simNextWeekModel(recap, facts);
      return (
        <Page>
          <HeroZone>
            {n.opponent ? <SimTeamLogo name={n.opponent} size="hero" label /> : null}
            <Hero value={n.opponent ?? `Week ${n.week ?? ""}`} caption={n.week != null ? `Week ${n.week}${n.opponent ? " opponent" : ""}` : undefined} />
            {n.yours != null && n.theirs != null ? (
              <p className="text-lg font-bold tabular-nums">
                <span style={{ color: "var(--color-accent)" }}>{simFmtPts(n.yours)}</span> <span style={{ color: "var(--color-text-muted)" }}>proj vs</span> {simFmtPts(n.theirs)}
              </p>
            ) : null}
            {n.edge ? <p className="text-sm font-semibold" style={{ color: "var(--color-text-secondary)" }}>{n.edge}</p> : null}
          </HeroZone>
          <RecapCard model={recapCardModel({ kicker: `Week ${n.week ?? ""} plan`.trim(), rows: recapRowsFromItems(n.notes.map((note) => ({ ...note, tone: note.label === "Lineup" ? ("warning" as const) : undefined }))) })} />
        </Page>
      );
    }
    return null;
  };

  const pages: StoryPage[] = keys.map((key, i) => ({
    key,
    label: `${title}${total > 1 ? ` · ${index + 1} of ${total}` : ""} · ${KICKER[key]}`,
    header: simRecapPageTitle(key, recap, { roundLabel: recap.kind === "playoff" ? simPlayoffRoundLabel(recap.week, ctx.game.settings) : null, youId: facts.youId }),
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
