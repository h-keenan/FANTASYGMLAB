"use client";

import { useState } from "react";

import { Sheet } from "@/components/ui/Sheet";
import {
  simAttributeText,
  simGradeAria,
  simGradeFill,
  simGradeLegend,
  simGradeRangeText,
  simGradeText,
  simGradeTone,
  type SimAttributeGrade,
  type SimGradeInput,
  type SimGradeTone,
} from "@/lib/simGrade";

/** The ramp: green, cyan, gold, orange, red, from existing semantic tokens only. */
const TONE_COLOR: Record<SimGradeTone, string> = {
  success: "var(--color-success)",
  accent: "var(--color-accent)",
  gold: "var(--color-action)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
};

const SIZE = { xs: { h: 18, min: 24, font: "0.75rem" }, sm: { h: 24, min: 34, font: "0.8125rem" }, md: { h: 32, min: 44, font: "1rem" }, lg: { h: 48, min: 64, font: "1.5rem" } } as const;

/**
 * The Fantasy Sim's overall: a Madden / 2K style letter grade instead of the numeric OVR gauge
 * (docs/ui-patterns.md, "Fantasy Sim letter grades"). A tinted capsule, same recipe as PlayerBadge: the tone tints the
 * fill and the ring, the TEXT stays the primary text colour mixed lightly with the tone so contrast holds in both
 * themes. A "?" marks a scouting estimate (rookies); the full read ("B plus, strong starter. Scouts are unsure: B to A
 * minus") is the accessible name and the tooltip. Reserves its footprint when there is no grade so list columns align.
 */
export function LetterGrade({ grade, size = "sm", testId = "letter-grade" }: { grade: SimGradeInput | null | undefined; size?: keyof typeof SIZE; testId?: string }) {
  const spec = SIZE[size];
  if (!grade?.grade) {
    return <span aria-hidden="true" style={{ display: "inline-block", minWidth: spec.min, height: spec.h }} data-testid={`${testId}-empty`} />;
  }
  const color = TONE_COLOR[simGradeTone(grade.grade)];
  const label = simGradeAria(grade);
  const range = simGradeRangeText(grade);
  // xs is the inline tile of a row's stats line: a small rounded square, the scouting "?" a dim superscript (never "A-?" in a capsule).
  const tile = size === "xs";
  return (
    <span
      role="img"
      aria-label={label}
      title={range ? `${label}` : label}
      data-testid={testId}
      data-grade={grade.grade}
      className="inline-flex shrink-0 flex-col items-center justify-center font-extrabold leading-none"
      style={{
        minWidth: spec.min,
        height: spec.h,
        padding: tile ? "0 5px" : "0 8px",
        borderRadius: tile ? "6px" : "var(--radius-pill)",
        fontSize: spec.font,
        background: `color-mix(in srgb, ${color} var(--chip-fill-pct, 15%), transparent)`,
        boxShadow: `inset 0 0 0 1.5px color-mix(in srgb, ${color} 55%, transparent)`,
        color: `color-mix(in srgb, ${color} 55%, var(--color-text-primary))`,
      }}
    >
      {tile && grade.grade_uncertain ? (
        <span aria-hidden="true">
          {grade.grade}
          <sup style={{ fontSize: "0.5625rem", opacity: 0.65, marginLeft: 1, fontWeight: 700 }}>?</sup>
        </span>
      ) : (
        <span aria-hidden="true">{simGradeText(grade)}</span>
      )}
      {size === "lg" && range ? (
        <span aria-hidden="true" className="mt-0.5 text-[0.6875rem] font-bold" style={{ color: "var(--color-text-muted)" }}>
          {range}
        </span>
      ) : null}
    </span>
  );
}

/** One attribute row: label, a coarse bar tinted by the grade tone, and the letter. */
export function GradeBar({ attribute }: { attribute: SimAttributeGrade }) {
  const color = TONE_COLOR[simGradeTone(attribute.grade)];
  const label = `${attribute.label}: ${simGradeAria({ grade: attribute.grade, grade_uncertain: attribute.uncertain })}`;
  return (
    <div className="flex items-center gap-3" role="img" aria-label={label} data-testid="grade-bar" data-attr={attribute.key}>
      <span className="w-24 shrink-0 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>
        {attribute.label}
      </span>
      <span className="relative h-2 min-w-0 flex-1 overflow-hidden" style={{ borderRadius: "var(--radius-pill)", background: "color-mix(in srgb, var(--color-text-muted) 18%, transparent)" }} aria-hidden="true">
        <span className="absolute inset-y-0 left-0" style={{ width: `${simGradeFill(attribute.grade)}%`, background: color, borderRadius: "var(--radius-pill)" }} />
      </span>
      <span className="w-9 shrink-0 text-right text-sm font-extrabold" aria-hidden="true">
        {simAttributeText(attribute)}
      </span>
    </div>
  );
}

/** The legend sheet: every grade and what it means, and what the "?" and the attributes are. */
export function GradeLegendSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Sheet open={open} onClose={onClose} title="What the grades mean">
      <p className="pb-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
        A grade is the scouts&apos; read of a player against his position, not an exact number: two players can share a grade, and a
        scout can be off by a step. A &quot;?&quot; means the scouts are unsure (rookies), so the grade could land a step either side.
      </p>
      <ul className="flex flex-col" data-testid="grade-legend">
        {simGradeLegend().map((row) => (
          <li key={row.grade} className="flex items-center gap-3 py-2" style={{ borderBottom: "1px solid color-mix(in srgb, var(--color-border) 55%, transparent)" }}>
            <LetterGrade grade={{ grade: row.grade }} testId="legend-grade" />
            <span className="text-sm">{row.meaning}</span>
          </li>
        ))}
      </ul>
      <p className="pt-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
        Attribute bars (Production, Volume, Durability and so on) come from usage and history and are graded on their own. They do not add up to
        the overall.
      </p>
    </Sheet>
  );
}

/** A small "Key" button for a list header: opens the legend sheet. */
export function GradeLegendButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-label="What the grades mean" className="inline-flex items-center justify-center gap-1 text-xs font-bold" style={{ color: "var(--color-text-muted)", minHeight: "var(--touch-target-min)", minWidth: "var(--touch-target-min)" }}>
        <span aria-hidden="true">ⓘ</span>
        <span>Grades</span>
      </button>
      <GradeLegendSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}

/** The quick view hero's grade tile: the big grade, tappable to open the legend (44px target). */
export function GradeTile({ grade }: { grade: SimGradeInput | null | undefined }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="pqv-stat-tile" aria-label={`${simGradeAria(grade)}. What the grades mean`} data-testid="hero-grade" style={{ minHeight: "var(--touch-target-min)" }}>
        <LetterGrade grade={grade} size="lg" testId="hero-letter-grade" />
        <span className="pqv-stat-tile-caption">Grade</span>
      </button>
      <GradeLegendSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}
