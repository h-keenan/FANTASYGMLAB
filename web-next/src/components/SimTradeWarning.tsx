"use client";

import { useState } from "react";

import { SimGlyph } from "./SimGlyph";

/**
 * A compact, dismissible warning for the trade builder: a small amber alert glyph, plain text, and Dismiss. Amber is only the glyph (this
 * is a true warning); the words stay in the normal text colour. A new message re-shows it. Twin of mobile/src/components/SimTradeWarning.tsx.
 */
export function SimTradeWarning({ message }: { message: string }) {
  const [dismissed, setDismissed] = useState<string | null>(null);
  if (!message || dismissed === message) return null;
  return (
    <div className="flex items-start gap-2 rounded-lg border px-2.5 py-2" style={{ borderColor: "var(--color-border)", background: "transparent" }} role="status" data-testid="trade-warning">
      <span style={{ color: "var(--color-warning)", marginTop: 2 }} aria-hidden="true"><SimGlyph name="alert" size={14} /></span>
      <p className="min-w-0 flex-1 text-xs" style={{ color: "var(--color-text)" }}>{message}</p>
      <button type="button" className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }} onClick={() => setDismissed(message)}>Dismiss</button>
    </div>
  );
}
