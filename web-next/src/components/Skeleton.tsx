import type { CSSProperties, ReactNode } from "react";

import { SlowLoadNote } from "@/components/SlowLoadNote";
import { pageTabFamily, type PageTabFamilyKey } from "@/lib/pageFamilies";
import { avatarSize, type AvatarTier } from "@/lib/playerAnatomy";

/**
 * The shared skeleton set (web twin of mobile SkeletonBlock / SkeletonCard /
 * SkeletonRows). Every per-layout skeleton is composed from these so the
 * shimmer, radius and spacing are defined once (`.pqv-skeleton-line` in
 * globals.css; the shimmer stops under `prefers-reduced-motion`). Decorative:
 * every composite below is `aria-hidden`; a page-level skeleton (`SkeletonPage`
 * or a template's `loading` prop) adds ONE `role="status"` name.
 *
 * Content-shaped sets (docs/ui-patterns.md, "Loading identity"): avatar circle,
 * header, hero, tab strip, module, player row, trade card, whole page. The
 * shared templates (CompactModule, PlayerAccordionRow, TradeCompactCard,
 * StatusHeader, PageTabBar) take a `loading` prop and render these, so a
 * loading page keeps the exact silhouette of the loaded one. This file is the
 * only place that may draw a loading placeholder (see skeletonScan.test.ts);
 * mobile twin: mobile/src/components/Skeleton.tsx.
 */
export function SkeletonBlock({
  width = "100%",
  height = 16,
  radius,
  className = "",
  style,
  ...rest
}: {
  width?: number | string;
  height?: number | string;
  radius?: string;
  className?: string;
  style?: CSSProperties;
  "data-fgl-this-week-trade-pending"?: string;
}) {
  return (
    <div
      aria-hidden="true"
      className={`pqv-skeleton-line ${className}`.trim()}
      style={{ width, height, ...(radius ? { borderRadius: radius } : {}), ...style }}
      {...rest}
    />
  );
}

/** A glass card holding `lines` text-line blocks (last one shorter). */
export function SkeletonCard({ lines = 3, className = "", style }: { lines?: number; className?: string; style?: CSSProperties }) {
  return (
    <div className={`glass-surface flex flex-col gap-3 p-4 ${className}`.trim()} style={style} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <SkeletonBlock key={index} width={index === lines - 1 ? "60%" : "100%"} height={index === 0 ? 18 : 14} />
      ))}
    </div>
  );
}

/** Avatar-left, two-line-right list rows. */
export function SkeletonRows({ count = 5 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="flex items-center gap-3">
          <SkeletonBlock width={40} height={40} radius="var(--radius-pill)" />
          <div className="flex flex-1 flex-col gap-2">
            <SkeletonBlock width="70%" height={14} />
            <SkeletonBlock width="45%" height={11} />
          </div>
        </div>
      ))}
    </div>
  );
}

/** The round placeholder where a player (or team) avatar will be. Sizes follow the avatar density tiers. */
export function SkeletonAvatar({ tier = "row", size }: { tier?: AvatarTier; size?: number }) {
  const px = size ?? avatarSize(tier);
  return <SkeletonBlock width={px} height={px} radius="var(--radius-pill)" style={{ flexShrink: 0 }} />;
}

/** A PlayerAccordionRow silhouette: avatar, name + meta lines, one trailing number. Same 44px minimum as the real row. */
export function SkeletonPlayerRow({ tier = "row", trailing = true, className = "" }: { tier?: AvatarTier; trailing?: boolean; className?: string }) {
  return (
    <div className={`flex min-w-0 items-center gap-2.5 ${className}`.trim()} style={{ minHeight: "var(--touch-target-min)", padding: "0.125rem 0.5rem" }} aria-hidden="true" data-testid="skeleton-player-row">
      <SkeletonAvatar tier={tier} />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <SkeletonBlock width="55%" height={14} />
        <SkeletonBlock width="38%" height={11} />
      </div>
      {trailing ? <SkeletonBlock width={34} height={26} /> : null}
    </div>
  );
}

/** A stack of player rows with the real list's hairlines. */
export function SkeletonPlayerRows({ count = 4, tier = "row" }: { count?: number; tier?: AvatarTier }) {
  return (
    <div className="flex flex-col" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} style={index === 0 ? undefined : { borderTop: "1px solid color-mix(in srgb, var(--color-border) 55%, transparent)" }}>
          <SkeletonPlayerRow tier={tier} />
        </div>
      ))}
    </div>
  );
}

/** A page title + one muted subtitle line (PageTitle / Header). */
export function SkeletonHeader({ subtitle = true }: { subtitle?: boolean }) {
  return (
    <div className="flex flex-col gap-2" aria-hidden="true" data-testid="skeleton-header">
      <SkeletonBlock width="52%" height={26} />
      {subtitle ? <SkeletonBlock width="34%" height={12} /> : null}
    </div>
  );
}

/**
 * The top tab strip (PageTabBar / PillRow glass): `count` pills in a glass bar. Hidden on phones, like the real
 * PageTabBar (its tabs live in the bottom pill there, which is derived from the route and never loads).
 */
export function SkeletonTabs({ count = 4 }: { count?: number }) {
  return (
    <div className="glass-surface flex items-center gap-2 overflow-hidden p-1.5 max-md:hidden" style={{ minHeight: "var(--touch-target-min)", borderRadius: "var(--radius-pill)" }} aria-hidden="true" data-testid="skeleton-tabs">
      {Array.from({ length: count }, (_, index) => (
        <SkeletonBlock key={index} height={32} radius="var(--radius-pill)" style={{ flex: 1, minWidth: 0 }} />
      ))}
    </div>
  );
}

/** The hero zone (Today / team status / player hero): a ring-or-avatar, kicker, headline and a supporting line in one glass card. */
export function SkeletonHero({ minHeight = 150 }: { minHeight?: number }) {
  return (
    <div className="glass-surface flex items-center gap-3 p-4" style={{ minHeight }} aria-hidden="true" data-testid="skeleton-hero">
      <SkeletonAvatar size={54} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <SkeletonBlock width="30%" height={10} />
        <SkeletonBlock width="80%" height={18} />
        <SkeletonBlock width="60%" height={13} />
      </div>
    </div>
  );
}

/** A CompactModule silhouette: title line, one or two summary lines, the expand mark. */
export function SkeletonModule({ lines = 2, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`glass-surface flex min-w-0 flex-col gap-1.5 p-3 ${className}`.trim()} style={{ borderLeft: "var(--border-width-semantic) solid var(--color-border)", minHeight: "var(--touch-target-min)" }} aria-hidden="true" data-testid="skeleton-module">
      <SkeletonBlock width="28%" height={10} />
      {Array.from({ length: Math.max(1, Math.min(2, lines)) }, (_, index) => (
        <SkeletonBlock key={index} width={index === 0 ? "88%" : "58%"} height={13} />
      ))}
    </div>
  );
}

/** A TradeCompactCard silhouette: title, a give and a get side of avatar rows, the fairness meter. */
export function SkeletonTradeCard({ assets = 2 }: { assets?: number }) {
  return (
    <div className="glass-surface flex min-w-0 flex-col gap-2 p-3" style={{ borderRadius: "var(--radius-panel)" }} aria-hidden="true" data-testid="skeleton-trade-card">
      <SkeletonBlock width="46%" height={14} />
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {[0, 1].map((side) => (
          <div key={side} className="flex min-w-0 flex-col gap-1">
            <SkeletonBlock width="24%" height={10} />
            {Array.from({ length: side === 0 ? assets : Math.max(1, assets - 1) }, (_, index) => (
              <SkeletonPlayerRow key={index} tier="card" trailing={false} />
            ))}
          </div>
        ))}
      </div>
      <SkeletonBlock height={8} radius="var(--radius-pill)" />
    </div>
  );
}

/** A StatusHeader silhouette: ring + headline, three mini stats, three player rows, the primary button. */
export function SkeletonStatusHeader({ rows = 3 }: { rows?: number }) {
  return (
    <div className="glass-surface flex flex-col gap-3 p-4" style={{ borderLeft: "var(--border-width-semantic) solid var(--color-border)" }} aria-hidden="true" data-testid="skeleton-status-header">
      <div className="flex items-center gap-3">
        <SkeletonAvatar size={54} />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <SkeletonBlock width="30%" height={10} />
          <SkeletonBlock width="78%" height={16} />
          <SkeletonBlock width="55%" height={12} />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[0, 1, 2].map((index) => (
          <SkeletonBlock key={index} height={46} radius="var(--radius-card, 12px)" />
        ))}
      </div>
      <SkeletonPlayerRows count={rows} />
      <SkeletonBlock height={44} radius="var(--radius-control)" />
    </div>
  );
}

/** One named loading region: the single `role="status"` a screen reader hears. Wrap composites in it when no template owns the name. */
export function SkeletonRegion({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div role="status" aria-busy="true" aria-label={`Loading ${label}`} className={className}>
      {children}
      <SlowLoadNote />
    </div>
  );
}

export type SkeletonLayout = "dashboard" | "list" | "detail" | "cards";

/**
 * A whole page, content-shaped: header, optional tab strip, then the body for the page's family. It is what every route
 * shows while auth or its first fetch resolves (LoadingScreen wraps it), so the page frame never flashes a splash and
 * then rebuilds. `list`: player rows (Players, Waivers, Roster); `dashboard`: status header + modules (Today, Team);
 * `cards`: trade cards (Trade Hub / Finder / History); `detail`: hero + modules (a player or league page).
 */
export function SkeletonPage({ label, layout = "dashboard", family }: { label: string; layout?: SkeletonLayout; family?: PageTabFamilyKey }) {
  const tabs = family ? pageTabFamily(family).tabs.length : 0;
  return (
    <main className="page-shell" aria-busy="true" data-testid="skeleton-page" data-layout={layout}>
      <SkeletonRegion label={label} className="flex flex-col gap-[var(--page-gap,1rem)]">
        <SkeletonHeader />
        {tabs > 0 ? <SkeletonTabs count={tabs} /> : null}
        {layout === "dashboard" ? (
          <>
            <SkeletonStatusHeader />
            <SkeletonModule />
            <SkeletonModule />
            <SkeletonModule />
          </>
        ) : null}
        {layout === "list" ? (
          <>
            <SkeletonBlock height={44} radius="var(--radius-control)" />
            <div className="glass-surface p-2">
              <SkeletonPlayerRows count={7} />
            </div>
          </>
        ) : null}
        {layout === "cards" ? (
          <>
            <SkeletonTradeCard />
            <SkeletonTradeCard />
            <SkeletonTradeCard assets={1} />
          </>
        ) : null}
        {layout === "detail" ? (
          <>
            <SkeletonHero />
            <SkeletonModule />
            <SkeletonModule />
            <SkeletonModule />
          </>
        ) : null}
      </SkeletonRegion>
    </main>
  );
}

/** Inline text-line placeholder for a small region that is still loading (a tab body, a sheet section). Names itself once for screen readers. */
export function SkeletonText({ lines = 3, label, className = "" }: { lines?: number; label: string; className?: string }) {
  return (
    <SkeletonRegion label={label} className={`flex flex-col gap-2 ${className}`.trim()}>
      {Array.from({ length: lines }, (_, index) => (
        <SkeletonBlock key={index} width={index === lines - 1 ? "55%" : index === 0 ? "92%" : "78%"} height={13} />
      ))}
    </SkeletonRegion>
  );
}

/** Player-row skeleton with its own status name: the loading body of a list region. */
export function SkeletonList({ label, count = 4, tier = "row" }: { label: string; count?: number; tier?: AvatarTier }) {
  return (
    <SkeletonRegion label={label}>
      <SkeletonPlayerRows count={count} tier={tier} />
    </SkeletonRegion>
  );
}
