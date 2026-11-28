"use client";

import { useState, type CSSProperties, type ReactNode } from "react";

/**
 * A helper paragraph condensed to ONE line with tap-for-more: the whole line is the toggle (aria-expanded), the text
 * stays in the DOM so search and screen readers still get it. Mobile twin: mobile/src/components/SimMoreNote.tsx.
 */
export function SimMoreNote({ children, testId, className = "text-[13px] leading-snug", style }: { children: ReactNode; testId?: string; className?: string; style?: CSSProperties }) {
  const [open, setOpen] = useState(false);
  return (
    <button
      type="button"
      aria-expanded={open}
      onClick={() => setOpen((v) => !v)}
      data-testid={testId}
      className={`block w-full min-w-0 text-left ${className}`}
      style={{
        color: "var(--color-text-secondary)",
        ...(open ? null : { display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical", overflow: "hidden" }),
        ...style,
      }}
    >
      {children}
    </button>
  );
}
