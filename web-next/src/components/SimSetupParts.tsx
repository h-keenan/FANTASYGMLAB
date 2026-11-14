"use client";

import type { ReactNode } from "react";

import { MotionIn } from "@/components/Motion";
import { SimGlyph } from "@/components/SimGlyph";
import { Toggle } from "@/components/Toggle";
import { SIM_DIFFICULTY_COPY, type SimDifficulty } from "@/lib/simGame";
import { SIM_DIFFICULTY_CARDS, SIM_SETUP_CARDS, type SimSetupCardId } from "@/lib/simSetupView";

/**
 * Building blocks of the Fantasy Sim "New game" form: glass section cards (icon + title + live one-line summary),
 * labelled fields with readable helper text, switch rows that live inside a card, selectable difficulty tiles and the
 * live "your league" summary. Shared glass surface, tokens and motion only (docs/ui-patterns.md); the mobile twin is
 * mobile/src/components/SimSetupParts.tsx and both read lib/simSetupView.ts.
 */

const HELP_STYLE = { color: "var(--color-text-secondary)" } as const;

/** A glass section: icon chip, title, a one-line summary that follows the options, then the controls. */
export function SetupCard({ id, summary, index = 0, count = 1, children }: { id: SimSetupCardId; summary: string; index?: number; count?: number; children: ReactNode }) {
  const card = SIM_SETUP_CARDS[id];
  return (
    <MotionIn index={index} count={count}>
      <section className="glass-surface flex flex-col gap-4 p-4 min-w-0" aria-labelledby={`sim-setup-${id}`} data-testid={`sim-setup-card-${id}`}>
        <header className="flex items-center gap-3 min-w-0">
          <span
            aria-hidden="true"
            className="inline-flex shrink-0 items-center justify-center"
            style={{
              width: 36,
              height: 36,
              borderRadius: "var(--radius-control)",
              color: "var(--color-accent)",
              background: "color-mix(in srgb, var(--color-accent) 14%, transparent)",
              border: "1px solid color-mix(in srgb, var(--color-accent) 30%, transparent)",
            }}
          >
            <SimGlyph name={card.glyph} size={18} />
          </span>
          <div className="min-w-0 flex flex-col">
            <h3 id={`sim-setup-${id}`} className="text-base font-extrabold leading-tight">{card.title}</h3>
            <p className="text-[13px] leading-snug truncate" style={{ color: "var(--color-accent)" }} data-testid={`sim-setup-summary-${id}`}>{summary}</p>
          </div>
        </header>
        {children}
      </section>
    </MotionIn>
  );
}

/** A labelled control with a readable helper line (13px, secondary ink). */
export function SetupField({ label, note, children, id }: { label: string; note?: string; children: ReactNode; id?: string }) {
  return (
    <div className="flex flex-col gap-2 min-w-0">
      <span className="text-sm font-bold" id={id}>{label}</span>
      {children}
      {note ? <p className="text-[13px] leading-snug" style={HELP_STYLE}>{note}</p> : null}
    </div>
  );
}

/** A quiet helper paragraph inside a card. */
export function SetupNote({ children, testId }: { children: ReactNode; testId?: string }) {
  return <p className="text-[13px] leading-snug" style={HELP_STYLE} data-testid={testId}>{children}</p>;
}

/** Switch rows grouped in one inset tile with hairline dividers, so toggles never float loose. */
export function SetupToggleGroup({ children }: { children: ReactNode }) {
  return (
    <div className="glass-input flex flex-col min-w-0" style={{ padding: "0 var(--space-md)" }} role="group">
      {children}
    </div>
  );
}

export function SetupToggleRow({ label, note, checked, onChange, first = false }: { label: string; note: string; checked: boolean; onChange: (next: boolean) => void; first?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2" style={first ? undefined : { borderTop: "1px solid var(--glass-input-border)" }}>
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-bold">{label}</span>
        <span className="text-[13px] leading-snug" style={HELP_STYLE}>{note}</span>
      </div>
      <Toggle checked={checked} onChange={onChange} label={label} />
    </div>
  );
}

/** Three tappable difficulty tiles with a short descriptor each; the chosen one gets the cyan glass glow. */
export function DifficultyTiles({ values, active, onSelect }: { values: SimDifficulty[]; active: SimDifficulty; onSelect: (value: SimDifficulty) => void }) {
  return (
    <div role="radiogroup" aria-label="Difficulty" className="flex flex-col gap-2">
      {values.map((value) => {
        const on = value === active;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onSelect(value)}
            className="flex items-center gap-3 text-left min-w-0"
            data-selected={on ? "true" : "false"}
            style={{
              minHeight: "var(--touch-target-min)",
              padding: "var(--space-sm) var(--space-md)",
              borderRadius: "var(--radius-control)",
              border: `1px solid ${on ? "var(--color-accent)" : "var(--glass-input-border)"}`,
              background: on ? "color-mix(in srgb, var(--color-accent) 12%, var(--glass-input-bg))" : "var(--glass-input-bg)",
              boxShadow: on ? "0 0 0 1px color-mix(in srgb, var(--color-accent) 35%, transparent), 0 0 18px color-mix(in srgb, var(--color-accent) 22%, transparent)" : "none",
              transition: "background var(--motion-fast) var(--ease-out), box-shadow var(--motion-fast) var(--ease-out), border-color var(--motion-fast) var(--ease-out)",
            }}
          >
            <span
              aria-hidden="true"
              className="inline-flex shrink-0 items-center justify-center"
              style={{
                width: 20,
                height: 20,
                borderRadius: "var(--radius-pill)",
                border: `2px solid ${on ? "var(--color-accent)" : "var(--color-border-strong)"}`,
                background: on ? "var(--color-accent)" : "transparent",
                color: "var(--color-on-accent)",
              }}
            >
              {on ? <SimGlyph name="check" size={12} /> : null}
            </span>
            <span className="flex flex-col min-w-0">
              <span className="text-sm font-extrabold">
                {SIM_DIFFICULTY_COPY[value].label}
                <span className="font-semibold" style={{ color: on ? "var(--color-accent)" : "var(--color-text-secondary)" }}> · {SIM_DIFFICULTY_CARDS[value].tagline}</span>
              </span>
              <span className="text-[13px] leading-snug" style={HELP_STYLE}>{SIM_DIFFICULTY_CARDS[value].detail}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** The live "your league" card: gold kicker, the headline sentence, glass chips, then the detail line(s). */
export function SetupSummaryCard({ headline, chips, detail, testId }: { headline: string; chips: string[]; detail: string; testId: string }) {
  return (
    <MotionIn>
      <section
        className="glass-surface premium-glow-card flex flex-col gap-3 p-4 min-w-0"
        aria-label="Your league"
        data-testid="sim-setup-hero"
        style={{ borderTop: "3px solid var(--color-accent)" }}
      >
        <p className="text-xs uppercase font-extrabold" style={{ color: "var(--color-premium)", letterSpacing: "var(--letter-spacing-badge)" }}>Your league</p>
        <p className="text-lg font-extrabold leading-snug" aria-live="polite">{headline}</p>
        <ul className="flex flex-wrap gap-2" aria-label="League at a glance">
          {chips.map((chip) => (
            <li
              key={chip}
              className="text-[13px] font-bold"
              style={{
                padding: "4px 12px",
                borderRadius: "var(--radius-pill)",
                color: "var(--color-accent)",
                background: "color-mix(in srgb, var(--color-accent) 12%, transparent)",
                border: "1px solid color-mix(in srgb, var(--color-accent) 30%, transparent)",
              }}
            >
              {chip}
            </li>
          ))}
        </ul>
        <p className="text-[13px] leading-snug" style={HELP_STYLE} data-testid={testId}>{detail}</p>
      </section>
    </MotionIn>
  );
}

/** Sticky action bar: stays above the safe area while the form scrolls. */
export function SetupStickyBar({ children, warning }: { children: ReactNode; warning?: string | null }) {
  return (
    <div
      className="sticky bottom-0 z-10 -mx-4 px-4 pt-3 flex flex-col gap-2"
      data-testid="sim-setup-bar"
      style={{
        paddingBottom: "max(var(--space-md), env(safe-area-inset-bottom))",
        background: "var(--glass-bg)",
        backdropFilter: "blur(28px) saturate(180%)",
        borderTop: "1px solid var(--glass-border)",
      }}
    >
      {warning ? <p className="text-[13px]" role="status" style={{ color: "var(--color-warning)" }}>{warning}</p> : null}
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}
