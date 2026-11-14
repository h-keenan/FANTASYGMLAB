"use client";

import { useId, useState, type ReactNode } from "react";

import { LetterGrade } from "@/components/ui/LetterGrade";
import { simGradeIndex, type SimGradeLetter } from "@/lib/simGrade";
import { AccentCard } from "@/components/AccentCard";
import type { RecapCardModel, RecapCardRow, RecapTone } from "@/lib/recapCard";

/**
 * THE recap card (7b V2): a glass card with the page kicker, an optional grade/finish badge and three label/value rows;
 * extra rows open under "More". Used on the StoryCarousel recap pages and the Season in Review stats. Cyan / neutral
 * glass; the badge uses the accent, never gold (gold is for premium meaning). Mobile twin: components/RecapCard.tsx.
 */
const TONE: Record<RecapTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
  muted: "var(--color-text-primary)",
};

function Row({ row, extra }: { row: RecapCardRow; extra?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1" data-testid="recap-card-row">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {row.label}
        </span>
        <span className="min-w-0 break-words text-right text-sm font-extrabold" style={{ color: TONE[row.tone ?? "muted"] }}>
          {row.value}
        </span>
      </div>
      {row.sub ? (
        <span className="text-right text-xs" style={{ color: "var(--color-text-muted)" }}>
          {row.sub}
        </span>
      ) : null}
      {extra}
    </div>
  );
}

export function RecapCard({ model, extras, testId = "recap-card" }: { model: RecapCardModel; /** Extra node under a row, by row key (a player chip). */ extras?: Record<string, ReactNode>; testId?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <AccentCard accent="var(--color-accent)" as="section" compact data-testid={testId}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {model.kicker}
        </span>
        {model.badge && simGradeIndex(model.badge) >= 0 ? (
          <span data-testid="recap-card-badge"><LetterGrade grade={{ grade: model.badge as SimGradeLetter }} size="sm" /></span>
        ) : model.badge ? (
          <span
            data-testid="recap-card-badge"
            className="inline-flex min-w-9 items-center justify-center px-2 text-sm font-extrabold"
            style={{ height: 30, borderRadius: "var(--radius-pill)", color: "var(--color-accent)", background: "color-mix(in srgb, var(--color-accent) 15%, transparent)", boxShadow: "inset 0 0 0 1.5px color-mix(in srgb, var(--color-accent) 55%, transparent)" }}
          >
            {model.badge}
          </span>
        ) : null}
      </div>
      <div className="flex flex-col gap-2">
        {model.rows.map((row) => (
          <Row key={row.key} row={row} extra={extras?.[row.key]} />
        ))}
      </div>
      {model.more.length > 0 ? (
        <>
          <button type="button" data-story-interactive aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} className="tap-link self-stretch text-xs font-bold" style={{ minHeight: "var(--touch-target-min)", color: "var(--color-accent)" }}>
            {open ? "Less" : `More (${model.more.length})`}
          </button>
          {open ? (
            <div id={id} className="flex flex-col gap-2" style={{ borderTop: "var(--border-width-default) solid var(--color-border)", paddingTop: 8 }}>
              {model.more.map((row) => (
                <Row key={row.key} row={row} extra={extras?.[row.key]} />
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </AccentCard>
  );
}
