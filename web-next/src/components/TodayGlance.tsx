"use client";

import Link from "next/link";
import { useId, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { PositionBadge } from "@/components/PositionBadge";
import { Collapse } from "@/components/ui/Presence";
import type { TodayRoomChip, TodayStandingPart } from "@/lib/todayView";

const TONE = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
  muted: "var(--color-text-primary)",
} as const;

const KICKER_STYLE = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" } as const;

/**
 * The standing as ONE slim line under "Do this now" ("8th of 12 · 6-4 · Playoffs 72% · Rank #3", model:
 * lib/todayView.ts todayStandingLine). A single link to My Team, which hosts the rank bars, position rooms and tiles.
 * Mobile twin: components/TodayGlance.tsx.
 */
export function TodayStandingLine({ parts, href }: { parts: TodayStandingPart[]; href: string }) {
  if (parts.length === 0) return null;
  return (
    <Link href={href} aria-label={`${parts.map((p) => p.text).join(", ")}. Open My Team`} className="glass-surface flex items-center gap-2 px-3" style={{ minHeight: 44, borderRadius: "var(--radius-card, 12px)", color: "inherit", textDecoration: "none" }} data-testid="today-tiles">
      <span className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 text-sm font-bold">
        {parts.map((p, i) => (
          <span key={p.key} className="inline-flex items-center gap-2" data-testid={`today-tile-${p.key}`}>
            {i > 0 ? <span aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>·</span> : null}
            <span style={{ color: TONE[p.tone === "muted" ? "muted" : p.tone] }}>{p.text}</span>
          </span>
        ))}
      </span>
      <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
        →
      </span>
    </Link>
  );
}

/**
 * Position rooms as small chips ("QB !  RB !  WR !  TE ✓") that open into one meter bar per room (concept C). The bars
 * draw the room's label, not a measurement. The weakest room links to Trade Hub. Mobile twin: components/TodayGlance.tsx.
 */
export function TodayRooms({ chips, tradeHref }: { chips: TodayRoomChip[]; tradeHref: string }) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  if (chips.length === 0) return null;
  const weakest = chips.find((c) => c.weakest);
  return (
    <AccentCard accent={weakest ? "var(--color-warning)" : "var(--color-accent)"} as="section" compact data-testid="today-rooms">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={bodyId}
        aria-label={`Position rooms: ${chips.map((c) => `${c.position} ${c.label}`).join(", ")}. ${open ? "Collapse" : "Expand"}`}
        className="flex w-full items-center gap-2 text-left"
        style={{ minHeight: "var(--touch-target-min)", color: "inherit" }}
      >
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-[0.6875rem] font-extrabold uppercase" style={KICKER_STYLE}>
            Position rooms
          </span>
          <span className="flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span
                key={c.position}
                className="inline-flex items-center gap-1 px-2 text-xs font-extrabold"
                style={{ borderRadius: "var(--radius-pill)", minHeight: 24, border: `1px solid ${TONE[c.tone === "muted" ? "muted" : c.tone]}`, color: c.tone === "muted" ? "var(--color-text-secondary)" : TONE[c.tone], background: `color-mix(in srgb, ${c.tone === "muted" ? "var(--color-text-muted)" : TONE[c.tone]} 10%, transparent)` }}
                data-testid={`today-room-chip-${c.position}`}
              >
                {c.position}
                {c.mark === "!" ? <span aria-hidden="true">!</span> : c.mark === "check" ? <span aria-hidden="true">✓</span> : null}
              </span>
            ))}
          </span>
        </span>
        <span aria-hidden="true" className="shrink-0 text-sm" style={{ color: "var(--color-accent)" }}>
          {open ? "Hide" : "Expand"} {open ? "⌃" : "⌄"}
        </span>
      </button>
      <Collapse open={open} id={bodyId}>
        <ul className="m-0 flex list-none flex-col gap-2 p-0 pt-1" data-testid="today-room-bars">
          {chips.map((c) => (
            <li key={c.position} className="grid items-center gap-2" style={{ gridTemplateColumns: "2rem minmax(0,1fr) auto" }}>
              <PositionBadge position={c.position} />
              <span className="h-2 overflow-hidden" style={{ borderRadius: "var(--radius-pill)", background: "var(--color-surface-muted)" }} role="img" aria-label={`${c.position} room: ${c.label}`}>
                <span className="block h-full" style={{ width: `${Math.round(c.fill * 100)}%`, background: c.tone === "muted" ? "var(--color-text-muted)" : TONE[c.tone] }} />
              </span>
              <span className="text-xs font-bold" style={{ color: c.tone === "muted" ? "var(--color-text-secondary)" : TONE[c.tone] }}>
                {c.label}
              </span>
            </li>
          ))}
        </ul>
        {weakest ? (
          <Link href={tradeHref} className="tap-link mt-1 inline-flex items-center text-sm font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)", textDecoration: "none" }}>
            Improve {weakest.position} first: Trade Hub ideas →
          </Link>
        ) : null}
      </Collapse>
    </AccentCard>
  );
}
