"use client";

import { PlayerName } from "@/components/PlayerName";
import { createContext, useContext, useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { Collapsible } from "@/components/Collapsible";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerListRow } from "@/components/PlayerListRow";
import { PlayerIdentity } from "@/components/PlayerRow";
import type { PlayerListStat, PlayerListTag } from "@/lib/playerListRow";
import { simDraftMeta, simDraftRowChips } from "@/lib/simDraft";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { SectionHeading } from "@/components/SectionHeading";
import { SheetHandle } from "@/components/SheetHandle";
import { SimCrest } from "@/components/SimCrest";
import { SimGlyph } from "@/components/SimGlyph";
import { ReviewGlyphIcon } from "@/components/SimReviewGlyph";
import { ToneBadge } from "@/components/ToneBadge";
import {
  simFmtPts,
  simTrendText,
  simPlayerSubline,
  simGamePreviewLine,
  simNoticeGlyph,
  simHeadshotId,
  simPlayerInitials,
  type SimGlyphName,
  type SimPlayerRef,
  type SimGame,
  type SimGameEnvelope,
  type SimGamePlayer,
  type SimGamePreview,
  type SimGameTone,
} from "@/lib/simGame";
import { TapForWhy } from "@/components/ui/TapForWhy";
import { simSeeAllLabel } from "@/lib/simLayout";

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

// Two columns only where both fit comfortably; a phone in landscape or a tablet stays single-column.
const WIDE_QUERY = "(min-width: 1100px)";

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
  /** Open any team's scouting sheet (roster, record, strengths and needs). */
  openTeam: (teamId: string) => void;
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
 * A trade/market value (the 0-100 number AI teams use in trades) with its real name and a tap-for-why
 * explainer. Never labeled plain "Value" or "VAL": the player's Overall is a different number.
 */
export function SimTradeValue({ value }: { value: number | null | undefined }) {
  if (value == null || Number.isNaN(value)) return null;
  const rounded = Math.round(value);
  return (
    <TapForWhy metric="trade_value" spoken={`Trade value ${rounded}`}>
      <SimStat label="Trade value" value={rounded} />
    </TapForWhy>
  );
}

/**
 * The one identity block every game surface uses for a player, whether it is
 * a full list row or a mention inside a card (injury, MVP, waiver result,
 * feed move, draft pick, lineup alert): position badge, Sleeper headshot
 * with an initials fallback, name, team subline and the Out chip. `size`
 * picks the avatar (40 in list rows, 32 inside cards); the box is fixed, so
 * a photo that fails to load never shifts the row.
 */
export function SimPlayerChip({
  player,
  size = 32,
  muted = false,
  extra,
  hidePosition = false,
  className = "min-w-0",
  onOpen,
  quick = false,
}: {
  player: SimPlayerRef;
  size?: number;
  muted?: boolean;
  extra?: ReactNode;
  /** Drop the position chip when the row's slot label already says it. */
  hidePosition?: boolean;
  className?: string;
  /** Make the chip itself tappable with this handler (it must not already sit inside a button). */
  onOpen?: (player: SimGamePlayer) => void;
  /**
   * Make the chip tappable with the shared default: the game's player detail,
   * which is the main app's Player Quick View fed by the sim row (see
   * SimPlayerSheet), same for real and synthetic players. Use it
   * wherever a chip is a mention (trade builder, offers, feed), never inside
   * another button.
   */
  quick?: boolean;
}) {
  const openSheet = useContext(SimOpenPlayerContext);
  const real = simHeadshotId(player);
  const body = (
    <PlayerIdentity
      playerId={real}
      fallbackLabel={simPlayerInitials(player)}
      name={player.name}
      position={hidePosition ? null : player.pos}
      injuryStatus={player.status === "out" ? "Out" : null}
      muted={muted}
      avatarSize={size}
      className={className}
      after={extra}
    >
      {simPlayerSubline(player)}
    </PlayerIdentity>
  );
  const handler = onOpen ?? (quick && openSheet ? openSheet : null);
  if (!handler) return body;
  return (
    <button
      type="button"
      className="block min-w-0 text-left"
      aria-label={`${player.name}, ${player.pos}. Open player details`}
      onClick={(event) => {
        event.stopPropagation();
        handler(player as SimGamePlayer);
      }}
    >
      {body}
    </button>
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
  selected = false,
  extra,
  hidePosition = false,
  tags,
  stats,
  week = null,
}: {
  player: SimGamePlayer;
  trailing?: ReactNode;
  onOpen?: (player: SimGamePlayer) => void;
  /** Kept for callers that dimmed bench rows; a list row is never dimmed. */
  muted?: boolean;
  selected?: boolean;
  extra?: ReactNode;
  hidePosition?: boolean;
  tags?: PlayerListTag[];
  /** Labeled stat pills (PROJ / VAL ...); see simListStats. */
  stats?: PlayerListStat[];
  /** Current game week, to flag a bye that is close. Omit when unknown (the bye still shows). */
  week?: number | null;
}) {
  const [chip] = simDraftRowChips(player);
  return (
    <PlayerListRow
      testId="sim-player-line"
      name={player.name}
      position={hidePosition ? null : player.pos}
      headshotId={simHeadshotId(player)}
      fallbackLabel={simPlayerInitials(player)}
      meta={simDraftMeta(player, week)}
      chip={chip ? { label: chip.label, tone: chip.tone } : null}
      hurt={player.status === "out"}
      tags={tags}
      stats={stats}
      extra={extra}
      actions={trailing}
      selected={selected}
      onOpen={onOpen ? () => onOpen(player) : undefined}
      openLabel={`${player.name}, ${player.pos}. Open player details`}
    />
  );
}

/**
 * Shared "action in flight" guard for every game button. `run(fn)` flips
 * `pending` on in the same event (one frame to a spinner/disabled state), ignores
 * a second call while the first is still running (a synchronous ref, so a
 * double tap in one frame cannot double submit) and clears when it settles.
 * mobile/src/components/SimGameParts.tsx has the same hook.
 */
export function useSimPending() {
  const inflight = useRef(false);
  const [pending, setPending] = useState(false);
  const run = async <T,>(fn: () => T | Promise<T>): Promise<T | undefined> => {
    if (inflight.current) return undefined;
    inflight.current = true;
    setPending(true);
    try {
      return await fn();
    } finally {
      inflight.current = false;
      setPending(false);
    }
  };
  return { pending, run };
}

/**
 * An icon-only control for dense rows (queue, draft). The label is the
 * accessible name. Instant feedback: on press it shows a pressed state and, when
 * the handler returns a promise, a spinner and a disabled state until it
 * settles (a synchronous ref guard blocks a double tap in the same frame).
 */
export function SimIconButton({
  label,
  onClick,
  pressed,
  primary = false,
  disabled = false,
  busy = false,
  size = 40,
  width,
  children,
}: {
  label: string;
  onClick: () => void | Promise<unknown>;
  pressed?: boolean;
  primary?: boolean;
  disabled?: boolean;
  busy?: boolean;
  /** Height in px (also the width unless `width` is set). */
  size?: number;
  width?: number;
  children: ReactNode;
}) {
  const { pending, run } = useSimPending();
  const on = primary || pressed;
  const working = busy || pending;
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      aria-busy={working || undefined}
      disabled={disabled || working}
      onClick={(event) => {
        event.stopPropagation();
        void run(onClick);
      }}
      className="inline-flex shrink-0 items-center justify-center active:scale-95"
      style={{
        width: width ?? size,
        height: size,
        borderRadius: "var(--radius-control)",
        border: `var(--border-width-default) solid ${on ? "var(--color-accent)" : "transparent"}`,
        background: primary ? "var(--color-accent-strong)" : pressed ? "var(--color-accent-soft)" : "var(--color-surface-muted)",
        color: primary ? "var(--color-on-accent)" : on ? "var(--color-accent)" : "var(--color-text-secondary)",
        opacity: disabled && !working ? 0.5 : 1,
        cursor: disabled || working ? "default" : "pointer",
        transition: "transform 90ms ease-out",
      }}
    >
      {working ? <span aria-hidden="true" className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" /> : children}
    </button>
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
  const modalRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // Focus moves into the dialog on open and returns to the trigger on close.
    const previous = document.activeElement as HTMLElement | null;
    modalRef.current?.focus();
    return () => previous?.focus?.();
  }, []);
  const sheet = (
    <div
      className="pqv-backdrop"
      data-sheet-hideable="true"
      data-testid="sim-sheet-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div ref={modalRef} tabIndex={-1} className="pqv-modal" role="dialog" aria-modal="true" aria-labelledby={labelledBy} style={{ outline: "none" }}>
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
  // Portaled to <body>: a position:fixed backdrop inside a transformed or
  // filtered ancestor (the game's enter-rise cards, glass panels) is
  // positioned against that ancestor, not the viewport, which pushed the
  // claim dialog off-screen for players far down a long list.
  return typeof document === "undefined" ? sheet : createPortal(sheet, document.body);
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
        <ReviewGlyphChip glyph={simNoticeGlyph(tone)} tone={tone} size={24} />
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

/** "You give" / "You get" label: fixed semantic color (red out, green in) with a small swap glyph. */
export function SimSideLabel({ side, note }: { side: "give" | "get"; note?: string }) {
  const tone: SimGameTone = side === "give" ? "danger" : "success";
  return (
    <p className="flex items-center gap-1 text-xs uppercase font-extrabold" style={{ color: simToneColor(tone), letterSpacing: "var(--letter-spacing-badge)" }}>
      <ReviewGlyphIcon glyph="trade" size={14} />
      {side === "give" ? "You give" : "You get"}
      {note ? <span className="normal-case font-medium" style={{ color: "var(--color-text-muted)" }}>{note}</span> : null}
    </p>
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

// ---------------------------------------------------------------------------
// Color and glyph building blocks shared by every game screen

/** Opens the game's own player sheet; provided once by the game screen so a chip can fall back to it. */
export const SimOpenPlayerContext = createContext<((player: SimGamePlayer) => void) | null>(null);

/** Opens the team scouting sheet. Provided once by the game screen; a team link outside it is plain text. */
export const SimTeamOpenContext = createContext<((teamId: string) => void) | null>(null);

/**
 * A team's emblem and name as one tap target that opens its scouting sheet
 * (roster, record, strengths and needs) from anywhere: standings, matchup,
 * trade partner, league feed.
 */
export function SimTeamLink({
  teamId,
  name,
  isYou = false,
  size = 24,
  suffix,
  className = "",
  bold = true,
  hideName = false,
  stacked = false,
}: {
  teamId: string | null | undefined;
  name: string;
  isYou?: boolean;
  size?: number;
  suffix?: ReactNode;
  className?: string;
  bold?: boolean;
  /** Emblem only (the name is printed beside it); the tap target keeps the name for screen readers. */
  hideName?: boolean;
  /** Emblem above the name, centered (the matchup header). */
  stacked?: boolean;
}) {
  const open = useContext(SimTeamOpenContext);
  const body = (
    <>
      <SimCrest name={name} size={size} />
      {hideName ? null : (
        <span className={`min-w-0 break-words text-sm ${bold ? "font-bold" : "font-medium"}`}>
          {name}
          {isYou ? " (you)" : ""}
        </span>
      )}
      {suffix}
    </>
  );
  const layout = stacked ? "flex-col justify-center text-center gap-1" : "items-center gap-2";
  if (!open || !teamId) return <span className={`inline-flex min-w-0 ${layout} ${className}`}>{body}</span>;
  return (
    <button
      type="button"
      onClick={() => open(teamId)}
      className={`tap-link inline-flex min-w-0 ${layout} ${stacked ? "" : "text-left"} ${className}`}
      style={{ minHeight: "var(--touch-target-min)" }}
      aria-label={`${name}${isYou ? " (you)" : ""}. Open team`}
    >
      {body}
    </button>
  );
}

/**
 * A summary-first card: the shared Collapsible with a tinted glyph title and
 * an always-visible summary. Open by default on desktop (two columns have the
 * room) and closed on phones unless `openOnPhone`; the player's own toggle is
 * remembered per `id`.
 */
export function SimFold({
  id,
  glyph,
  tone = "accent",
  title,
  summary,
  openOnPhone = false,
  children,
  testId,
}: {
  id: string;
  glyph: SimGlyphName;
  tone?: SimGameTone;
  title: ReactNode;
  summary?: ReactNode;
  openOnPhone?: boolean;
  children: ReactNode;
  testId?: string;
}) {
  const wide = useSimWide();
  return (
    <Collapsible
      id={`${id}`}
      testId={testId}
      accent={simToneColor(tone)}
      defaultOpen={wide || openOnPhone}
      title={
        <span className="inline-flex items-center gap-2">
          <span className="inline-flex" style={{ color: simToneColor(tone) }}>
            <SimGlyph name={glyph} size={16} />
          </span>
          {title}
        </span>
      }
      summary={summary}
    >
      {children}
    </Collapsible>
  );
}

/** "See all (n more)" toggle under a previewed list. */
export function SimSeeAll({ hidden, expanded, onToggle, noun }: { hidden: number; expanded: boolean; onToggle: () => void; noun?: string }) {
  if (hidden <= 0 && !expanded) return null;
  return (
    <button
      type="button"
      className="tap-link self-start text-xs font-bold"
      style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
      aria-expanded={expanded}
      onClick={onToggle}
    >
      {simSeeAllLabel(hidden, expanded, noun)}
    </button>
  );
}

/** Section title with a tinted glyph, on the shared SectionHeading. */
export function SimSectionTitle({
  glyph,
  tone = "accent",
  children,
  note,
  action,
  id,
}: {
  glyph: SimGlyphName;
  tone?: SimGameTone;
  children: ReactNode;
  note?: string;
  action?: ReactNode;
  id?: string;
}) {
  const title = (
    <span className="inline-flex items-center gap-2">
      <span className="inline-flex" style={{ color: simToneColor(tone) }}>
        <SimGlyph name={glyph} size={16} />
      </span>
      {children}
    </span>
  );
  return (
    <SectionHeading id={id} size="compact" action={action} note={note}>
      {title}
    </SectionHeading>
  );
}

/** Green up / red down text for a points change. */
export function SimTrend({ delta, suffix = "" }: { delta: number | null | undefined; suffix?: string }) {
  const t = simTrendText(delta);
  return (
    <span className="inline-flex items-center gap-0.5 font-bold tabular-nums" style={{ color: simToneColor(t.tone) }} data-testid="sim-trend">
      {t.arrow ? <span aria-hidden="true" style={{ fontSize: "0.65em" }}>{t.arrow}</span> : null}
      {t.text}
      {suffix}
    </span>
  );
}

/** A compact photo + name + status chip for dense two-column surfaces (matchup, cover lists). */
export function SimMiniPlayer({
  player,
  align = "left",
  extra,
  onOpen,
  size = 28,
}: {
  /** @deprecated Names never wrap: they shorten to "F. Lastname" when tight (PlayerName). */
  wrap?: boolean;
  player: SimGamePlayer;
  align?: "left" | "right";
  extra?: ReactNode;
  onOpen?: (player: SimGamePlayer) => void;
  size?: number;
}) {
  const hurt = player.status === "out";
  const bye = player.status === "bye";
  const body = (
    <span className={`flex w-full min-w-0 items-center gap-2 ${align === "right" ? "flex-row-reverse text-right" : ""}`}>
      <PlayerAvatar playerId={simHeadshotId(player)} fallbackLabel={simPlayerInitials(player)} size={size} />
      <span className="flex min-w-0 flex-1 flex-col leading-tight">
        <PlayerName name={player.name} className="text-xs font-bold" style={{ color: hurt || bye ? "var(--color-text-muted)" : undefined, textDecoration: hurt ? "line-through" : undefined }} />
        <span className={`flex items-center gap-1 text-[0.6875rem] ${align === "right" ? "justify-end" : ""}`} style={{ color: "var(--color-text-muted)" }}>
          {hurt ? <SimToneBadge label="Out" tone="danger" /> : bye ? <SimToneBadge label="Bye" tone="warning" /> : <span className="truncate">{player.team ?? "FA"}</span>}
          {extra}
        </span>
      </span>
    </span>
  );
  if (!onOpen) return <span className="block min-w-0">{body}</span>;
  return (
    <button type="button" className="block w-full min-w-0 text-left" onClick={() => onOpen(player)} aria-label={`${player.name}, ${player.pos}. Open player details`}>
      {body}
    </button>
  );
}
