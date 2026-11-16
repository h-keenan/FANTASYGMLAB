"use client";

import Link from "next/link";
import { useId, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { PickAvatar } from "@/components/PickAvatar";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerName } from "@/components/PlayerName";
import { PositionBadge } from "@/components/PositionBadge";
import { InfoMark } from "@/components/ui/InfoMark";
import { Collapse } from "@/components/ui/Presence";
import { playerHeadshotId, playerInitials } from "@/lib/playerAnatomy";
import { tradeIdeaGainText } from "@/lib/tradeIdeaSummary";
import type { TodayRoomChip, TodayTile, TodayTradeAsset, TodayTradeIdea } from "@/lib/todayView";

const TONE = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
  muted: "var(--color-text-primary)",
} as const;

const KICKER_STYLE = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" } as const;

/**
 * The compact tile row under "Do this now": Standing, Playoffs, Trades. One tile per fact (the model is
 * lib/todayView.ts todayTiles); each is a link to the page that owns the detail. Mobile twin: components/TodayGlance.tsx.
 */
export function TodayTiles({ tiles, hrefs }: { tiles: TodayTile[]; hrefs: Record<TodayTile["key"], string> }) {
  if (tiles.length === 0) return null;
  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${tiles.length}, minmax(0, 1fr))` }} data-testid="today-tiles">
      {tiles.map((tile) => (
        <Link
          key={tile.key}
          href={hrefs[tile.key]}
          aria-label={`${tile.label.toLowerCase()}: ${tile.value} ${tile.sub}. Open`}
          className="glass-surface flex min-w-0 flex-col items-center justify-center gap-0.5 px-2 py-2 text-center"
          style={{ minHeight: 72, borderRadius: "var(--radius-card, 12px)", color: "inherit", textDecoration: "none" }}
          data-testid={`today-tile-${tile.key}`}
        >
          <span className="text-[0.6875rem] font-extrabold uppercase" style={KICKER_STYLE}>
            {tile.label}
          </span>
          <span className="text-2xl font-extrabold tabular-nums leading-none" style={{ color: TONE[tile.tone] }}>
            {tile.value}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {tile.sub}
          </span>
        </Link>
      ))}
    </div>
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

function TradeSide({ label, assets }: { label: string; assets: TodayTradeAsset[] }) {
  if (assets.length === 0) return null;
  return (
    <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
      <span className="w-9 shrink-0 text-[0.6875rem] font-extrabold uppercase" style={KICKER_STYLE}>
        {label}
      </span>
      {assets.slice(0, 2).map((a) => (
        <span key={`${a.id ?? a.name}`} className="inline-flex min-w-0 items-center gap-1.5">
          {a.isPick ? (
            <PickAvatar label={a.name} size={24} />
          ) : (
            <PlayerAvatar playerId={playerHeadshotId({ id: a.id, name: a.name })} tier={a.tier ?? undefined} size={24} fallbackLabel={playerInitials(a.name)} />
          )}
          {a.isPick ? <span className="text-sm font-bold">{a.name}</span> : <PlayerName name={a.name} className="min-w-0 text-sm font-bold" />}
          {a.position ? <PositionBadge position={a.position} /> : null}
        </span>
      ))}
      {assets.length > 2 ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          +{assets.length - 2}
        </span>
      ) : null}
    </span>
  );
}

/** The trade idea as one card (concept B): kicker, "Get a QB from Team Iron", who goes and who comes, the value gain. The whole card opens it in Trade Hub. */
export function TodayTradeIdeaCard({ idea, href, deadline, info }: { idea: TodayTradeIdea; href: string; /** "2 wks left (Wk 11)": the trade deadline, shown here and nowhere else. */ deadline?: string | null; /** Beginner explainer for the card's ONE "?", inline after the kicker. */ info?: string | null }) {
  const gain = idea.gain != null && idea.gain !== 0 ? tradeIdeaGainText(idea.gain) : null;
  return (
    <AccentCard accent="var(--color-action)" as="section" compact data-testid="today-trade-idea">
      {info ? (
        <div className="flex items-center">
          <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-action)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Trade idea{deadline ? ` · deadline ${deadline}` : ""}
          </span>
          <InfoMark label="trade ideas" lines={[info]} beginnerOnly />
        </div>
      ) : null}
      <Link href={href} aria-label={`Trade idea: ${idea.title}. Open in Trade Hub`} className="flex items-center gap-2" style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }}>
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="flex items-center gap-2">
            {info ? null : (
              <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-action)", letterSpacing: "var(--letter-spacing-badge)" }}>
                Trade idea{deadline ? ` · deadline ${deadline}` : ""}
              </span>
            )}
            {gain ? (
              <span className="text-xs font-extrabold tabular-nums" style={{ color: idea.gain != null && idea.gain > 0 ? "var(--color-success)" : "var(--color-danger)" }} data-testid="today-trade-gain">
                {gain} value
              </span>
            ) : null}
          </span>
          <span className="text-base font-extrabold leading-snug">{idea.title}</span>
          <TradeSide label="Send" assets={idea.send} />
          <TradeSide label="Get" assets={idea.receive} />
        </span>
        <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
          →
        </span>
      </Link>
    </AccentCard>
  );
}
