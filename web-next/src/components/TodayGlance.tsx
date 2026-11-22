"use client";

import Link from "next/link";
import { useId, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { PickAvatar } from "@/components/PickAvatar";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import { InfoMark } from "@/components/ui/InfoMark";
import { Collapse } from "@/components/ui/Presence";
import { playerHeadshotId, playerInitials } from "@/lib/playerAnatomy";
import { tradeGainLabel, type TodayRoomChip, type TodayTile, type TodayTradeAsset, type TodayTradeIdea } from "@/lib/todayView";

const TONE = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
  muted: "var(--color-text-primary)",
} as const;

const KICKER_STYLE = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" } as const;

/**
 * The one snapshot strip under "Do this now": Standing, Playoffs, Team rank (model: lib/todayView.ts todayTiles). It is a
 * single link: the whole strip opens My Team, which hosts the rank bars, position rooms and tiles. Mobile twin:
 * components/TodayGlance.tsx.
 */
export function TodaySnapshotStrip({ tiles, href }: { tiles: TodayTile[]; href: string }) {
  if (tiles.length === 0) return null;
  return (
    <Link href={href} aria-label={`${tiles.map((t) => `${t.label.toLowerCase()} ${t.value} ${t.sub}`).join(", ")}. Open My Team`} className="glass-surface flex items-stretch" style={{ minHeight: 56, borderRadius: "var(--radius-card, 12px)", color: "inherit", textDecoration: "none" }} data-testid="today-tiles">
      {tiles.map((tile, i) => (
        <span key={tile.key} className="flex min-w-0 flex-1 flex-col items-center justify-center gap-0 px-2 py-1.5 text-center" style={i > 0 ? { borderLeft: "var(--border-width-default) solid var(--color-border)" } : undefined} data-testid={`today-tile-${tile.key}`}>
          <span className="text-[0.6875rem] font-extrabold uppercase" style={KICKER_STYLE}>
            {tile.label}
          </span>
          <span className="text-lg font-extrabold tabular-nums leading-tight" style={{ color: TONE[tile.tone] }}>
            {tile.value}
          </span>
          <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>
            {tile.sub}
          </span>
        </span>
      ))}
      <span aria-hidden="true" className="flex items-center pr-3" data-row-arrow style={{ color: "var(--color-accent)" }}>
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

/**
 * The best trade as ONE compact row: avatars of who you send → who you get, and the gain in green. A trade that costs value
 * never reaches this row (lib/todayView.ts bestTradeIdea) and no negative or red figure is ever drawn. The row opens it
 * in Trade Hub. Mobile twin: components/TodayGlance.tsx.
 */
export function TodayTradeRow({ idea, href, deadline, info }: { idea: TodayTradeIdea; href: string; /** "2 wks left (Wk 11)": the trade deadline, shown here and nowhere else. */ deadline?: string | null; /** Beginner explainer for the row's ONE "?". */ info?: string | null }) {
  const gain = tradeGainLabel(idea);
  const faces = (assets: TodayTradeAsset[]) =>
    assets.slice(0, 2).map((a) =>
      a.isPick ? <PickAvatar key={a.name} label={a.name} size={28} /> : <PlayerAvatar key={a.id ?? a.name} playerId={playerHeadshotId({ id: a.id, name: a.name })} tier={a.tier ?? undefined} size={28} fallbackLabel={playerInitials(a.name)} />,
    );
  const names = (assets: TodayTradeAsset[]) => assets.map((a) => a.name).join(" + ");
  return (
    <AccentCard accent="var(--color-action)" as="section" compact data-testid="today-trade-idea">
      <div className="flex items-center gap-1">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-action)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Best trade{deadline ? ` · deadline ${deadline}` : ""}
        </span>
        {info ? <InfoMark label="trade ideas" lines={[info]} beginnerOnly /> : null}
      </div>
      <Link href={href} aria-label={`Best trade: ${idea.title}${gain ? `, ${gain} value` : ""}. Open in Trade Hub`} className="flex items-center gap-2" style={{ minHeight: 44, color: "inherit", textDecoration: "none" }}>
        <span className="flex shrink-0 items-center gap-1" aria-hidden="true">
          {faces(idea.send)}
          <span style={{ color: "var(--color-text-muted)" }}>→</span>
          {faces(idea.receive)}
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-bold leading-snug">{idea.title}</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {[idea.send.length > 0 ? names(idea.send) : null, idea.receive.length > 0 ? names(idea.receive) : null].filter(Boolean).join(" → ")}
          </span>
        </span>
        {gain ? (
          <span className="shrink-0 text-sm font-extrabold tabular-nums" style={{ color: "var(--color-success)" }} data-testid="today-trade-gain">
            {gain}
          </span>
        ) : null}
        <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
          →
        </span>
      </Link>
    </AccentCard>
  );
}
