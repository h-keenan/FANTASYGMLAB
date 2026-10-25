"use client";

import { useId, useState } from "react";

import { GLOSSARY, type GlossaryKey } from "@/lib/glossary";

/**
 * "ⓘ What do these mean?" under a row of jargon labels (Power Rank, Starter
 * Strength, ...). Tapping opens a short panel with one plain-language
 * sentence per term from the shared glossary (lib/glossary.ts), for every
 * account, not only beginners. One affordance per strip rather than one per
 * tile: a 4-up strip at 390px has no room for four tap targets. Mirrors
 * mobile's GlossaryNote.
 */
export function GlossaryNote({
  terms,
  label = "What do these mean?",
  className = "",
}: {
  terms: GlossaryKey[];
  label?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  if (terms.length === 0) return null;
  return (
    <div className={`flex flex-col gap-2 ${className}`.trim()} data-glossary-note="true">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={id}
        className="tap-link self-start gap-1 text-xs font-semibold"
        style={{ color: "var(--color-text-muted)", background: "none", border: "none", padding: 0, cursor: "pointer" }}
      >
        <span aria-hidden="true">ⓘ</span>
        {label}
      </button>
      {open ? (
        <dl id={id} className="glass-surface m-0 flex flex-col gap-2 p-3 text-xs">
          {terms.map((key) => (
            <div key={key} className="flex flex-col gap-0.5">
              <dt className="font-bold" style={{ color: "var(--color-text-primary)" }}>
                {GLOSSARY[key].label}
              </dt>
              <dd className="m-0" style={{ color: "var(--color-text-secondary)" }}>
                {GLOSSARY[key].definition}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
