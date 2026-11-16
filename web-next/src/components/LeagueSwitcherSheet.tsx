"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { LeagueCrest } from "@/components/LeagueCrest";
import { PillRow } from "@/components/PillRow";
import { SkeletonBlock } from "@/components/Skeleton";
import { Sheet } from "@/components/ui/Sheet";
import { VALUATION_LENS_OPTIONS, useValuationLens } from "@/context/ValuationLensContext";
import { filterLeagues, SWITCHER_SEARCH_FROM } from "@/lib/appHeader";
import { markOverlayNavigating } from "@/lib/overlayHistory";
import { swapLeagueIdInPath } from "@/lib/leagueSwitcher";
import type { SavedLeagueRow, SavedLeaguesStatus } from "@/lib/useSavedLeagues";

/**
 * The league switcher (UI pass 6/7, coridian_ 2026-11-14: "10 v1"): a bottom sheet of league cards on the shared `Sheet` (so Escape, the
 * phone Back button, outside tap and swipe-down all close it through the overlay manager). League names wrap, never ellipsize; every league
 * has a crest (lib/leagueCrest.ts); search shows from 6 leagues; a failed load says so and offers Try again; Connect a league, the Fantasy Sim
 * games and the sample league live at the end; the evaluation lens is a segmented control. Mobile twin: components/LeagueSwitcherHeaderButton.tsx.
 */
export function LeagueSwitcherSheet({
  open,
  onClose,
  leagueId,
  leagueName,
  leagues,
  status,
  onRetry,
}: {
  open: boolean;
  onClose: () => void;
  leagueId: string;
  leagueName: string | null;
  leagues: SavedLeagueRow[];
  status: SavedLeaguesStatus;
  onRetry: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { lens, setLens } = useValuationLens(leagueId);
  const [query, setQuery] = useState("");
  // The current league is always listed, even before (or without) the saved list resolving it.
  const rows = leagues.some((r) => r.league_id === leagueId) ? leagues : [{ league_id: leagueId, league_name: leagueName }, ...leagues];
  const shown = filterLeagues(rows, query, leagueId);
  const lensHint = VALUATION_LENS_OPTIONS.find((o) => o.value === lens)?.hint;

  return (
    <Sheet open={open} onClose={onClose} title="Your leagues" description={status === "ready" ? `${rows.length} saved` : undefined} testId="league-switcher">
      <div className="flex flex-col gap-2">
        {rows.length >= SWITCHER_SEARCH_FROM ? (
          <Input type="search" aria-label="Search leagues" placeholder={`Search ${rows.length} leagues`} value={query} onChange={(e) => setQuery(e.target.value)} />
        ) : null}
        {status === "loading" && leagues.length === 0 ? (
          <div className="flex flex-col gap-2" aria-busy="true">
            <SkeletonBlock height={52} />
            <SkeletonBlock height={52} />
          </div>
        ) : null}
        {status === "error" ? (
          <div role="alert" className="flex flex-wrap items-center gap-2 text-sm" style={{ color: "var(--color-text-secondary)" }} data-testid="league-switcher-error">
            <span>Couldn&apos;t load your other leagues.</span>
            <Button variant="accentOutline" size="sm" onClick={onRetry}>
              Try again
            </Button>
          </div>
        ) : null}
        <ul className="flex flex-col" role="list">
          {shown.map((row) => {
            const current = row.league_id === leagueId;
            return (
              <li key={row.league_id}>
                <button
                  type="button"
                  aria-current={current ? "true" : undefined}
                  onClick={() => {
                    if (current) {
                      onClose();
                      return;
                    }
                    // A button, not a link: tell the overlay history a navigation is starting, or closing the sheet walks history Back over it.
                    markOverlayNavigating();
                    onClose();
                    const newPath = swapLeagueIdInPath(pathname || "", leagueId, row.league_id);
                    router.push(`${newPath}?name=${encodeURIComponent(row.league_name || row.league_id)}`);
                  }}
                  className="flex w-full items-center gap-3 px-2 py-2 text-left"
                  style={{
                    minHeight: 56,
                    borderRadius: "var(--radius-control)",
                    background: current ? "var(--color-accent-soft)" : "transparent",
                    borderBottom: current ? "none" : "var(--border-width-default) solid var(--color-border)",
                  }}
                  data-testid="league-row"
                >
                  <LeagueCrest leagueId={row.league_id} name={row.league_name} size={36} />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="break-words text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                      {row.league_name || row.league_id}
                    </span>
                    {current ? (
                      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                        Current league
                      </span>
                    ) : null}
                  </span>
                  {current ? (
                    <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
                      ✓
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
          {shown.length === 0 && query ? (
            <li className="px-2 py-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
              No league matches &ldquo;{query}&rdquo;.
            </li>
          ) : null}
        </ul>
        <div className="flex flex-col" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
          <SwitcherLink href="/connect-league" glyph="+" label="Connect a league" accent onDone={onClose} />
          <SwitcherLink href="/gm-game" glyph="FS" label="Fantasy Sim games" onDone={onClose} />
          <SwitcherLink href="/sample-league" glyph="★" label="Try the sample league" onDone={onClose} />
        </div>
        <div className="flex flex-col gap-1 pt-1">
          <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Evaluation lens
          </span>
          <PillRow variant="fill" ariaLabel="Evaluation lens" options={VALUATION_LENS_OPTIONS.map((o) => ({ label: o.label, value: o.value }))} active={lens} onSelect={(v) => setLens(v as typeof lens)} />
          {lensHint ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {lensHint}
            </span>
          ) : null}
        </div>
      </div>
    </Sheet>
  );
}

function SwitcherLink({ href, glyph, label, accent = false, onDone }: { href: string; glyph: string; label: string; accent?: boolean; onDone: () => void }) {
  return (
    <Link href={href} onClick={onDone} className="flex items-center gap-3 px-2 py-2" style={{ minHeight: 52 }}>
      <span aria-hidden="true" className="inline-flex shrink-0 items-center justify-center text-xs font-extrabold" style={{ width: 36, height: 36, borderRadius: "50%", border: "var(--border-width-default) solid var(--color-border-strong)", color: "var(--color-text-secondary)" }}>
        {glyph}
      </span>
      <span className="text-sm font-bold" style={{ color: accent ? "var(--color-accent)" : "var(--color-text-primary)" }}>
        {label}
      </span>
    </Link>
  );
}
