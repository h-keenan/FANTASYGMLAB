"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import type { SimMoveKind, SimMoveSpec } from "@/lib/simMove";

/** What a screen supplies: run one action (optionally with the chosen slot / taxi player). The strip never calls the API itself. */
export type SimMoveRun = (kind: SimMoveKind, targetKey?: string) => Promise<unknown> | void;

export interface SimMoveHandle {
  specs: SimMoveSpec[];
  run: SimMoveRun;
  /** The server's reason when it refused a move; shown under the strip. */
  refusal?: string | null;
}

/**
 * THE one trailing control of a sim roster row: a single Move button. It toggles the row's in-place expansion (the same
 * accordion state as tapping the row) and never carries more than an icon, so a name and its stats line keep the width.
 */
export function SimMoveButton({ name, open, onToggle }: { name: string; open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      aria-label={`Move ${name}`}
      aria-expanded={open}
      data-testid="move-button"
      onClick={onToggle}
      className="inline-flex shrink-0 items-center justify-center"
      style={{
        width: 40,
        height: 40,
        borderRadius: "var(--radius-control)",
        border: `var(--border-width-default) solid ${open ? "var(--color-accent)" : "transparent"}`,
        background: open ? "var(--color-accent-soft)" : "var(--color-surface-muted)",
        color: open ? "var(--color-accent)" : "var(--color-text-secondary)",
        transition: "transform 90ms ease-out",
      }}
    >
      <span aria-hidden="true" className="text-xl font-black leading-none" style={{ transform: open ? "rotate(90deg)" : undefined, transition: "transform 160ms ease-out" }}>⋯</span>
    </button>
  );
}

/**
 * The inline action strip an open roster row shows: only the actions that are possible right now (lib/simMove.ts), one of
 * them primary. An action with choices (a lineup slot, a taxi player) reveals chips for them; Cut asks "Cut Name?" with
 * Cut / Keep before it runs. No sheet: everything happens in the row.
 */
export function SimMoveStrip({ specs, run, refusal }: SimMoveHandle) {
  const [choosing, setChoosing] = useState<SimMoveKind | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  async function go(kind: SimMoveKind, key?: string) {
    if (busy) return;
    setBusy(key ? `${kind}:${key}` : kind);
    try {
      await run(kind, key);
    } finally {
      setBusy(null);
    }
  }

  const cut = specs.find((s) => s.kind === "cut");
  const picking = specs.find((s) => s.kind === choosing && s.targets);
  if (specs.length === 0) return null;

  return (
    <div className="flex flex-col gap-2" data-testid="move-strip">
      {confirming && cut ? (
        <div className="flex flex-wrap items-center gap-2" data-testid="move-cut-confirm">
          <span className="text-sm font-bold" style={{ color: "var(--color-danger)" }}>{cut.confirm}</span>
          <Button size="sm" variant="danger" loading={busy === "cut"} onClick={() => void go("cut")}>Cut</Button>
          <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => setConfirming(false)}>Keep</Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {specs.map((spec) => (
            <Button
              key={spec.kind}
              size="sm"
              variant={spec.primary ? "primary" : spec.danger ? "dangerOutline" : "secondary"}
              loading={busy === spec.kind}
              disabled={busy !== null && busy !== spec.kind}
              aria-expanded={spec.targets ? choosing === spec.kind : undefined}
              data-move={spec.kind}
              onClick={() => {
                if (spec.targets) setChoosing((cur) => (cur === spec.kind ? null : spec.kind));
                else if (spec.confirm) setConfirming(true);
                else void go(spec.kind);
              }}
            >
              {spec.label}
            </Button>
          ))}
        </div>
      )}
      {picking?.targets && !confirming ? (
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={picking.label} data-testid="move-targets">
          {picking.targets.map((t) => (
            <button
              key={t.key}
              type="button"
              disabled={busy !== null}
              data-target={t.key}
              onClick={() => void go(picking.kind, t.key)}
              className="inline-flex flex-col items-start justify-center px-2.5 text-left"
              style={{ minHeight: "var(--touch-target-min)", borderRadius: "var(--radius-control)", border: "var(--border-width-default) solid var(--color-border-strong)", background: "var(--color-surface-muted)", color: "var(--color-text-primary)" }}
            >
              <span className="text-xs font-extrabold leading-4">{t.label}</span>
              {t.hint ? <span className="text-[0.6875rem] leading-3" style={{ color: "var(--color-text-muted)" }}>{t.hint}</span> : null}
            </button>
          ))}
        </div>
      ) : null}
      {refusal ? (
        <p className="text-sm font-semibold" role="alert" style={{ color: "var(--color-warning)" }} data-testid="reserve-refusal">{refusal}</p>
      ) : null}
    </div>
  );
}
