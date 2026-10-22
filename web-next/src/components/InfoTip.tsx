"use client";

import { useId, useState, type ReactNode } from "react";

import { useExperienceCopy } from "@/context/ExperienceLevelContext";

/**
 * Shared "short label + ⓘ" affordance. Replaces always-visible explanatory
 * paragraphs: the label stays on screen, the full explanation opens on tap.
 * Beginner accounts (useExperienceCopy) see the full explanation inline.
 * Mirrors mobile's ScreenInfoNote.
 */
export function InfoTip({
  label,
  children,
  className = "",
  tone = "muted",
}: {
  label: string;
  children: ReactNode;
  className?: string;
  tone?: "muted" | "warning";
}) {
  const [open, setOpen] = useState(false);
  const copy = useExperienceCopy();
  const id = useId();
  const color = tone === "warning" ? "var(--color-warning)" : "var(--color-text-muted)";
  const expanded = open || copy.isBeginner;
  return (
    <div className={`flex flex-col gap-1 ${className}`.trim()} data-info-tip="true">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={expanded}
        aria-controls={id}
        className="inline-flex items-center gap-1 self-start text-xs font-semibold"
        style={{ color, background: "none", border: "none", padding: 0, cursor: "pointer" }}
      >
        <span aria-hidden="true">ⓘ</span>
        {label}
      </button>
      {expanded ? (
        <p id={id} className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {children}
        </p>
      ) : null}
    </div>
  );
}
