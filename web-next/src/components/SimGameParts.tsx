"use client";

import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { PlayerIdentity } from "@/components/PlayerRow";
import { SheetHandle } from "@/components/SheetHandle";
import { ToneBadge } from "@/components/ToneBadge";
import {
  simFmtPts,
  simPlayerSubline,
  simGamePreviewLine,
  type SimGame,
  type SimGameEnvelope,
  type SimGamePlayer,
  type SimGamePreview,
  type SimGameTone,
} from "@/lib/simGame";

/** Semantic color token for a presentation tone (never a raw hex). */
export function simToneColor(tone: SimGameTone): string {
  switch (tone) {
    case "success":
      return "var(--color-success)";
    case "warning":
      return "var(--color-warning)";
    case "danger":
      return "var(--color-danger)";
    case "accent":
      return "var(--color-accent)";
    default:
      return "var(--color-text-secondary)";
  }
}

const WIDE_QUERY = "(min-width: 1024px)";

function subscribeWide(callback: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
  const media = window.matchMedia(WIDE_QUERY);
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}

/** True on desktop-width viewports (two-column layouts); false on SSR and in jsdom. */
export function useSimWide(): boolean {
  return useSyncExternalStore(
    subscribeWide,
    () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(WIDE_QUERY).matches,
    () => false,
  );
}

/** What every game sub-screen needs from the controller. */
export interface SimCtx {
  gameId: string;
  game: SimGame;
  preview: SimGamePreview | null;
  call: <T extends SimGameEnvelope>(fn: () => Promise<T>) => Promise<T | null>;
  setGame: (game: SimGame) => void;
  reloadGame: () => Promise<void>;
  notify: (message: string, tone?: SimGameTone) => void;
  /** Bumped after any change that other panels should refetch for. */
  tick: number;
  bump: () => void;
  openPlayer: (player: SimGamePlayer) => void;
}

/** The shared status pill tinted from a presentation tone. */
export function SimToneBadge({ label, tone, size = "xs" }: { label: string; tone: SimGameTone; size?: "sm" | "xs" }) {
  return <ToneBadge label={label} color={simToneColor(tone)} size={size} />;
}

/** Debounce a changing value (search boxes). */
export function useSimDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

/** A label over a value: the one small stat used in every game screen. */
export function SimStat({ label, value, tone = "muted" }: { label: string; value: ReactNode; tone?: SimGameTone }) {
  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span className="text-sm font-bold" style={{ color: tone === "muted" ? "var(--color-text-primary)" : simToneColor(tone) }}>
        {value}
      </span>
    </div>
  );
}

/**
 * One player row for every game list (board, roster, waivers, trades, search):
 * the shared PlayerIdentity (position badge, headshot, name, subline with the
 * injury pill) with a trailing slot. Sim players are not real-league players,
 * so there is no quick view; the whole row is one tap target that opens the
 * game's own player sheet.
 */
export function SimPlayerLine({
  player,
  trailing,
  onOpen,
  muted = false,
  selected = false,
  extra,
}: {
  player: SimGamePlayer;
  trailing?: ReactNode;
  onOpen?: (player: SimGamePlayer) => void;
  muted?: boolean;
  selected?: boolean;
  extra?: ReactNode;
}) {
  const identity = (
    <PlayerIdentity
      playerId={player.id}
      name={player.name}
      position={player.pos}
      injuryStatus={player.status === "out" ? "Out" : null}
      muted={muted}
      className="flex-1 min-w-0"
      after={extra}
    >
      {simPlayerSubline(player)}
    </PlayerIdentity>
  );
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2"
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        background: selected ? "var(--color-accent-soft)" : undefined,
      }}
    >
      {onOpen ? (
        <button
          type="button"
          onClick={() => onOpen(player)}
          className="flex flex-1 items-center text-left"
          style={{ minHeight: "var(--touch-target-min)", minWidth: "min(100%, 12rem)" }}
          aria-label={`${player.name}, ${player.pos}. Open player details`}
        >
          {identity}
        </button>
      ) : (
        identity
      )}
      {trailing ? <div className="flex items-center gap-2 ml-auto">{trailing}</div> : null}
    </div>
  );
}

/** Projection + range stat for trailing slots. */
export function SimProjection({ player }: { player: SimGamePlayer }) {
  return <SimStat label="Proj" value={simFmtPts(player.projection)} />;
}

/**
 * The shared sheet shell (pqv-* classes: backdrop, glass modal, grab handle,
 * close X) the other detail sheets use, with Escape and scroll lock.
 */
export function SimSheet({ title, onClose, children, labelledBy = "sim-sheet-title" }: { title: string; onClose: () => void; children: ReactNode; labelledBy?: string }) {
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);
  return (
    <div
      className="pqv-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="pqv-modal" role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
        <SheetHandle />
        <button type="button" className="pqv-close" aria-label={`Close ${title}`} onClick={onClose}>
          ×
        </button>
        <div className="pqv-scroll">
          <h2 id={labelledBy} className="sr-only">
            {title}
          </h2>
          {children}
        </div>
      </div>
    </div>
  );
}

/** The free-preview strip over a game; nothing for Pro. */
export function SimPreviewBanner({ preview }: { preview: SimGamePreview | null | undefined }) {
  const line = simGamePreviewLine(preview);
  if (!line) return null;
  return (
    <AccentCard accent="var(--color-premium)" compact as="div">
      <div className="flex items-center gap-2">
        <ToneBadge label="Free preview" color="var(--color-premium)" size="xs" />
        <p className="text-xs flex-1 min-w-0" data-testid="sim-preview-line" style={{ color: "var(--color-text-secondary)" }}>
          {line}
        </p>
      </div>
    </AccentCard>
  );
}

/** A transient or blocking one-line message inside a game (role=status/alert). */
export function SimNotice({ message, tone = "warning", onDismiss }: { message: string; tone?: SimGameTone; onDismiss?: () => void }) {
  if (!message) return null;
  return (
    <AccentCard accent={simToneColor(tone)} compact as="div" className="enter-rise">
      <div className="flex items-start gap-2" role={tone === "danger" ? "alert" : "status"}>
        <p className="text-sm flex-1 min-w-0">{message}</p>
        {onDismiss ? (
          <button type="button" className="tap-link text-xs font-bold" style={{ color: "var(--color-accent)" }} onClick={onDismiss}>
            Dismiss
          </button>
        ) : null}
      </div>
    </AccentCard>
  );
}

/** Previous / next page controls. */
export function SimPager({ page, pages, onPage }: { page: number; pages: number; onPage: (page: number) => void }) {
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between gap-2">
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Page {page} of {pages}
      </span>
      <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </div>
  );
}
