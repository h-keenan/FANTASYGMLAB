"use client";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { SimCollapse } from "@/components/SimGameDynastyParts";
import { SimToneBadge, simToneColor } from "@/components/SimGameParts";
import { ReviewGlyphIcon } from "@/components/SimReviewGlyph";
import {
  simDynastySummaryView,
  simDynastyYearView,
  type SimDynastySummary,
  type SimDynastyYear,
  type SimDynastyYearView,
} from "@/lib/simGame";

/**
 * A small per-year strip: one cell per finished season with the year, record
 * and finish. Scrolls inside its own box, so the page never scrolls sideways.
 */
export function SimDynastyStrip({ years }: { years: SimDynastyYear[] }) {
  if (years.length === 0) return null;
  const views = years.map(simDynastyYearView);
  return (
    <section aria-label="Your seasons so far" data-testid="dynasty-strip">
      <ol className="flex gap-2 overflow-x-auto pb-1">
        {views.map((v) => (
          <li key={v.year} className="shrink-0">
            <div
              className="flex min-w-[5.5rem] flex-col gap-0.5 px-2 py-1.5"
              style={{
                borderRadius: "var(--radius-control)",
                border: "var(--border-width-default) solid var(--color-border)",
                borderTop: `3px solid ${v.youWon ? "var(--color-success)" : simToneColor(v.resultTone)}`,
                background: "var(--color-surface)",
              }}
            >
              <span className="flex items-center gap-1 text-xs font-extrabold">
                {v.year}
                {v.youWon ? <ReviewGlyphIcon glyph="trophy" size={12} /> : null}
              </span>
              <span className="text-xs tabular-nums" style={{ color: "var(--color-text-secondary)" }}>
                {v.record}
              </span>
              <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>
                {v.finish} · {v.result}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function YearRow({ v }: { v: SimDynastyYearView }) {
  return (
    <li className="flex flex-col gap-1 py-2" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }} data-testid="dynasty-year">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-extrabold">{v.year}</span>
        <span className="flex flex-wrap items-center justify-end gap-2">
          <span className="text-sm font-bold tabular-nums">{v.record}</span>
          <SimToneBadge label={`${v.finish} place`} tone="muted" />
          <SimToneBadge label={v.result} tone={v.resultTone} />
        </span>
      </div>
      <p className="flex items-center gap-1 text-xs" style={{ color: v.youWon ? "var(--color-success)" : "var(--color-text-muted)" }}>
        <ReviewGlyphIcon glyph="trophy" size={12} />
        Champion: {v.champion}
      </p>
      {v.scorers ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Top scorers: {v.scorers}
        </p>
      ) : null}
    </li>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span className="text-base font-extrabold tabular-nums">{value}</span>
    </div>
  );
}

/**
 * The dynasty result: titles, average finish, best season and a per-year
 * list. A dynasty game has no grade, so this stands where the grade card does.
 */
export function SimDynastyResult({ summary, onNewGame, onHub }: { summary: SimDynastySummary | null | undefined; onNewGame: () => void; onHub: () => void }) {
  const view = simDynastySummaryView(summary);
  const champion = view.titles > 0;
  return (
    <div className="flex flex-col gap-3" data-testid="dynasty-result">
      <AccentCard accent={champion ? "var(--color-success)" : "var(--color-accent)"} as="section" glow={champion}>
        <p className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Dynasty in review
        </p>
        <p className="flex items-center gap-2 text-2xl font-extrabold enter-pop" style={{ color: champion ? "var(--color-success)" : undefined }}>
          <ReviewGlyphIcon glyph="trophy" size={24} />
          {view.titlesLine}
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {view.seasonsLine}
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Fact label="Average finish" value={view.avgFinish} />
          <Fact label="Best season" value={view.bestSeason} />
          <Fact label="Playoff trips" value={view.trips} />
          <Fact label="Record" value={view.record} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={onNewGame}>Play again</Button>
          <Button variant="secondary" onClick={onHub}>
            All games
          </Button>
        </div>
      </AccentCard>
      <SimCollapse title="Season by season" summary={view.years.length ? `${view.years.length} seasons` : "No seasons yet"} defaultOpen testId="dynasty-years">
        {view.years.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            No finished seasons to show.
          </p>
        ) : (
          <ol className="flex flex-col">
            {view.years.map((v) => (
              <YearRow key={v.year} v={v} />
            ))}
          </ol>
        )}
      </SimCollapse>
    </div>
  );
}
