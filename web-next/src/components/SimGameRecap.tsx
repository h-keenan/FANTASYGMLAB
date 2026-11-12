"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { SimPlayerChip, SimPlayerLine, SimStat, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { SimStandingsList } from "@/components/SimGameLeague";
import { SkeletonCard } from "@/components/Skeleton";
import { SeasonReviewSections, ReviewDeltaText, ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { ReviewGlyphIcon } from "@/components/SimReviewGlyph";
import { SimReviewShareButton } from "@/components/SimReviewShareButton";
import { api } from "@/lib/api";
import { buildReviewShareModel } from "@/lib/simReview";
import {
  simFmtPts,
  normalizeSimResult,
  simGameReasonMessage,
  simSlotRepeatsPosition,
  simGradeTone,
  simPlayoffOutcomeTone,
  simPlayoffResultLabel,
  simPlayoffRoundLabel,
  simResultLabel,
  simResultTone,
  simSlotLabels,
  simTeamNameMap,
  type SimGameResult,
  type SimWeekRecap,
} from "@/lib/simGame";

/** One week's recap: the score lands first, then your starters, the league and what changed. */
export function SimWeekRecapView({
  recap,
  index,
  total,
  ctx,
  onNext,
  onClose,
}: {
  recap: SimWeekRecap;
  index: number;
  total: number;
  ctx: SimCtx;
  onNext: () => void;
  onClose: () => void;
}) {
  const names = simTeamNameMap(ctx.game.you ? [{ team_id: ctx.game.you.team_id, name: ctx.game.you.name }] : []);
  const game = recap.your_game;
  const youId = ctx.game.you?.team_id;
  const title = recap.kind === "playoff" ? `${simPlayoffRoundLabel(recap.week, ctx.game.settings)} recap` : `Week ${recap.week} recap`;
  const slotLabels = game ? simSlotLabels(game.starters.map((s) => ({ slot: s.slot }))) : [];
  const last = index + 1 >= total;
  const tone = simResultTone(game?.result);
  return (
    <div className="flex flex-col gap-3" data-testid="week-recap">
      <AccentCard accent={simToneColor(tone)} as="section" glow={game?.result === "win"}>
        <p className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {title}
          {total > 1 ? ` · ${index + 1} of ${total}` : ""}
        </p>
        {game ? (
          <div className="flex flex-col gap-2 enter-pop" key={recap.week}>
            <div className="flex items-center justify-between gap-3">
              <SimToneBadge label={simResultLabel(game.result)} tone={tone} size="sm" />
              <span className="text-xs break-words min-w-0 text-right" style={{ color: "var(--color-text-muted)" }}>vs {game.opponent_name}</span>
            </div>
            <div className="flex items-baseline justify-center gap-3" aria-label={`You ${simFmtPts(game.your_pts)}, ${game.opponent_name} ${simFmtPts(game.opp_pts)}`}>
              <span className="text-4xl font-extrabold" style={{ color: simToneColor(tone) }}>{simFmtPts(game.your_pts)}</span>
              <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>to</span>
              <span className="text-3xl font-bold" style={{ color: "var(--color-text-secondary)" }}>{simFmtPts(game.opp_pts)}</span>
            </div>
            {game.optimal_pts != null ? (
              <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
                Your best possible lineup scored {simFmtPts(game.optimal_pts)}
                {game.efficiency != null ? ` (${Math.round(game.efficiency * 100)}% efficiency)` : ""}.
              </p>
            ) : null}
          </div>
        ) : (
          <p className="text-base font-bold">You had a bye this week.</p>
        )}
        {recap.season_complete ? (
          <p className="flex items-center gap-2 text-sm font-bold" role="status" style={{ color: "var(--color-success)" }}>
            <ReviewGlyphChip glyph="trophy" tone="success" size={24} />
            The season is over{recap.champion ? ` and ${names[recap.champion] ?? "the champion"} won it all` : ""}.
          </p>
        ) : null}
      </AccentCard>

      {game ? (
        <section className="flex flex-col gap-1" aria-label="Your starters">
          <SectionHeading><span className="inline-flex items-center gap-2"><ReviewGlyphChip glyph="lineup" tone="accent" size={24} />Your starters</span></SectionHeading>
          {game.starters.map((s, i) => (
            <div key={`${s.slot}-${i}`} className="flex items-center gap-2">
              <span className="w-12 shrink-0">
                <PositionBadge position={s.slot} label={slotLabels[i]} />
              </span>
              <div className="flex-1 min-w-0">
                {s.player ? (
                  <SimPlayerLine
                    player={s.player}
                    hidePosition={simSlotRepeatsPosition(s.slot, s.player.pos)}
                    trailing={
                      <>
                        {s.flag ? <SimToneBadge label={s.flag === "bye" ? "Bye" : "Out"} tone={s.flag === "bye" ? "warning" : "danger"} /> : null}
                        <SimStat label="Pts" value={simFmtPts(s.pts)} tone={s.pts >= s.player.projection ? "success" : "muted"} />
                      </>
                    }
                  />
                ) : (
                  <p className="py-2 text-sm" style={{ color: "var(--color-warning)" }}>Empty slot (0 points)</p>
                )}
              </div>
            </div>
          ))}
        </section>
      ) : null}

      {recap.mvp || recap.bust ? (
        <div className="grid grid-cols-2 gap-2">
          {recap.mvp ? (
            <AccentCard accent="var(--color-success)" compact as="div">
              <span className="flex items-center gap-1.5 text-xs font-bold" style={{ color: "var(--color-success)" }}><ReviewGlyphChip glyph="boom" tone="success" size={22} />Week MVP</span>
              <SimPlayerChip player={recap.mvp.player} />
              <ReviewDeltaText text={`${simFmtPts(recap.mvp.pts)} pts`} tone="success" size="sm" />
            </AccentCard>
          ) : null}
          {recap.bust ? (
            <AccentCard accent="var(--color-warning)" compact as="div">
              <span className="flex items-center gap-1.5 text-xs font-bold" style={{ color: "var(--color-warning)" }}><ReviewGlyphChip glyph="bust" tone="warning" size={22} />Biggest bust</span>
              <SimPlayerChip player={recap.bust.player} />
              <ReviewDeltaText text={`${simFmtPts(recap.bust.pts)} pts`} tone="warning" size="sm" />
            </AccentCard>
          ) : null}
        </div>
      ) : null}

      {(recap.injuries ?? []).length > 0 ? (
        <section className="flex flex-col gap-1" aria-label="Injuries">
          <SectionHeading><span className="inline-flex items-center gap-2"><ReviewGlyphChip glyph="injury" tone="danger" size={24} />Injuries</span></SectionHeading>
          {recap.injuries!.map((inj, i) => (
            <AccentCard key={i} accent={inj.is_yours ? "var(--color-danger)" : "var(--color-border-strong)"} compact as="div">
              <SimPlayerChip player={{ ...inj.player, status: "out", out_weeks: inj.weeks }} />
              <p className="flex flex-wrap items-center gap-2 text-xs font-semibold" style={{ color: "var(--color-danger)" }}>
                <span>Out {inj.weeks} week{inj.weeks === 1 ? "" : "s"}</span>
                {inj.is_yours ? <SimToneBadge label="Your team" tone="danger" /> : null}
              </p>
            </AccentCard>
          ))}
        </section>
      ) : null}

      {(recap.waivers ?? []).filter((w) => w.team_id === youId).length > 0 ? (
        <section className="flex flex-col gap-1" aria-label="Your waiver claims">
          <SectionHeading><span className="inline-flex items-center gap-2"><ReviewGlyphChip glyph="waiver" tone="success" size={24} />Your waiver claims</span></SectionHeading>
          {recap.waivers!.filter((w) => w.team_id === youId).map((w, i) => (
            <AccentCard key={i} accent={w.ok ? "var(--color-success)" : "var(--color-danger)"} compact as="div">
              <SimPlayerChip player={w.add} />
              <p className="flex flex-wrap items-center gap-2 text-xs">
                <SimToneBadge label={w.ok ? "Won" : "Lost"} tone={w.ok ? "success" : "danger"} />
                {w.drop ? <span className="font-semibold" style={{ color: "var(--color-danger)" }}>dropping {w.drop.name}</span> : null}
                {!w.ok && w.reason ? <span style={{ color: "var(--color-text-muted)" }}>({w.reason.replace(/_/g, " ")})</span> : null}
              </p>
            </AccentCard>
          ))}
        </section>
      ) : null}

      {(recap.standings ?? []).length > 0 ? (
        <section className="flex flex-col gap-2" aria-label="Standings after this week">
          <SectionHeading><span className="inline-flex items-center gap-2"><ReviewGlyphChip glyph="rank" tone="accent" size={24} />Standings</span></SectionHeading>
          <SimStandingsList rows={recap.standings!} playoffTeams={ctx.game.settings.playoff_teams} />
        </section>
      ) : null}

      <div className="flex gap-2 sticky bottom-16 md:bottom-2">
        {!last ? (
          <Button fullWidth onClick={onNext}>Next round</Button>
        ) : (
          <Button fullWidth onClick={onClose}>{recap.season_complete ? "See your final grade" : "Back to your team"}</Button>
        )}
      </div>
    </div>
  );
}

/** Final screen: champion, record, grade and the decisions that mattered. */
export function SimFinalView({ ctx, onNewGame, onHub }: { ctx: SimCtx; onNewGame: () => void; onHub: () => void }) {
  const { gameId, game } = ctx;
  const [result, setResult] = useState<SimGameResult | null>(null);
  const [failed, setFailed] = useState(false);
  const [failMessage, setFailMessage] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimGameResult(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.result) setResult(body.result);
        else {
          setFailMessage(simGameReasonMessage(body.reason, body));
          setFailed(true);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, attempt]);

  if (failed) {
    return <EmptyState title="Could not load your final result" subtitle={failMessage || "Your season is saved. Try again in a moment."} actionLabel="Try again" onAction={() => { setFailed(false); setFailMessage(""); setAttempt((n) => n + 1); }} />;
  }
  if (!result) return <div className="flex flex-col gap-3" aria-busy="true"><SkeletonCard lines={4} /><SkeletonCard lines={6} /></div>;

  const view = normalizeSimResult(result);
  const tone = simGradeTone(view.letter);
  const mine = view.mine;
  const youWon = Boolean(view.championId && view.championId === mine?.team_id);
  const record = mine ? `${mine.wins}-${mine.losses}${mine.ties ? `-${mine.ties}` : ""}` : "";
  const outcomeTone = simPlayoffOutcomeTone(mine?.playoff_result);
  const shareModel = buildReviewShareModel({
    letter: view.letter,
    gradeTone: tone,
    headline: youWon ? `Champions! ${record}` : mine ? `${record}, ${simPlayoffResultLabel(mine.playoff_result)}` : "Season complete",
    subline: view.championName && !youWon ? `${view.championName} won the title` : view.summaryText,
    sections: view.sections,
  });
  return (
    <div className="flex flex-col gap-3" data-testid="final-result">
      <AccentCard accent={simToneColor(tone)} as="section" glow>
        <p className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>Season in review</p>
        <div className="flex items-center gap-4 enter-pop">
          <span className="text-6xl font-extrabold leading-none" style={{ color: simToneColor(tone) }} aria-label={`Grade ${view.letter}`}>
            {view.letter || "-"}
          </span>
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              {record ? <span className="text-lg font-extrabold tabular-nums">{record}</span> : null}
              {mine ? <SimToneBadge label={simPlayoffResultLabel(mine.playoff_result)} tone={outcomeTone} size="sm" /> : null}
            </div>
            {view.championName ? (
              <p className="flex items-center gap-1 text-xs" style={{ color: youWon ? "var(--color-success)" : "var(--color-text-muted)" }}>
                <ReviewGlyphIcon glyph="trophy" size={14} />
                Champion: {view.championName}{youWon ? " (you)" : ""}
              </p>
            ) : null}
          </div>
        </div>
        {view.summaryText ? <p className="text-sm">{view.summaryText}</p> : null}
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={onNewGame}>Play again</Button>
          <Button variant="secondary" onClick={onHub}>All games</Button>
          <SimReviewShareButton model={shareModel} sections={view.sections} gameId={gameId} />
        </div>
      </AccentCard>

      <SeasonReviewSections sections={view.sections} />

      <section className="flex flex-col gap-2" aria-label="Final standings">
        <SectionHeading>
          <span className="inline-flex items-center gap-2"><ReviewGlyphChip glyph="rank" tone="accent" size={24} />Final standings</span>
        </SectionHeading>
        <ol className="flex flex-col gap-2">
          {view.standings.map((row, i) => (
            <li key={row.team_id}>
              <AccentCard accent={row.is_you ? "var(--color-accent)" : simToneColor(simPlayoffOutcomeTone(row.playoff_result))} compact as="div">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold break-words min-w-0">{i + 1}. {row.name}{row.is_you ? " (you)" : ""}</span>
                  <span className="text-sm font-bold shrink-0 tabular-nums">{row.wins}-{row.losses}{row.ties ? `-${row.ties}` : ""}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <SimToneBadge label={simPlayoffResultLabel(row.playoff_result)} tone={simPlayoffOutcomeTone(row.playoff_result)} />
                  <span className="text-xs tabular-nums" style={{ color: "var(--color-text-secondary)" }}>{simFmtPts(row.pf)} PF</span>
                </div>
              </AccentCard>
            </li>
          ))}
        </ol>
      </section>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        A game, not a forecast. Season {game.settings.regular_weeks} weeks plus playoffs against AI managers; nothing here touches your real leagues.
      </p>
    </div>
  );
}
