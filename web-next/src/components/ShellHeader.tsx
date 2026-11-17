"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import dynamic from "next/dynamic";
import { useEffect, useState, type ReactNode } from "react";

import { LeagueCrest } from "@/components/LeagueCrest";
import { SHELL_PAGE_INFO_SLOT_ID } from "@/components/PageTitle";
import { headerShowsTitle, headerSlotsFor, headerTemplateFor, ribbonCollapsed, type HeaderChip } from "@/lib/appHeader";
import { useHeaderChips } from "@/lib/headerContext";
import { PAGE_TITLE_BY_SEGMENT } from "@/lib/navDestinations";
import { shellLeagueContext, shellParent } from "@/lib/shellNav";
import { TERMS } from "@/lib/terms";
import { useSavedLeagues } from "@/lib/useSavedLeagues";
import { useSearchParams } from "@/lib/useSearchParams";
import { useShellNav } from "@/lib/useShellNav";
import { UNNAMED_LEAGUE } from "@/lib/leagueName";
import { VALUATION_LENS_OPTIONS, useValuationLens } from "@/context/ValuationLensContext";

const CHIP_COLOR: Record<string, string> = {
  accent: "var(--color-accent)",
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-secondary)",
};

/**
 * THE phone header (UI pass 7, coridian_ picked direction V2, the context ribbon). Two templates share one component:
 *  - root (a tab page: Today, Team, Trades, League and their tabs, News, Portfolio): the bottom pill already names the page, so the header
 *    does NOT repeat it (rule 1, lib/appHeader.ts). It is league identity: the crest, the league name (wraps, never ellipsized) and the lens,
 *    one tap opens the league switcher sheet; search and the bell; and a ribbon of glanceable chips the page registers (useHeaderContext)
 *    that folds away after 24px of scroll.
 *  - detail (a page nothing else names): back (named for the parent), the page title, the "?" slot, a small crest that opens the switcher,
 *    search and the bell.
 * Phones only; Header hides its own row below 768px when this renders, so there is exactly one header.
 */
// The switcher sheet (with its pill row) is only needed once the crest is tapped, so its code loads on first open instead of in
// every route's first-load JS.
export const LeagueSwitcherSheet = dynamic(() => import("@/components/LeagueSwitcherSheet").then((m) => m.LeagueSwitcherSheet), { ssr: false });

export function ShellHeader({ actions }: { actions: ReactNode }) {
  const { barVisible } = useShellNav();
  const pathname = usePathname();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const chips = useHeaderChips();
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [switcherSeen, setSwitcherSeen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const { leagueId, leagueName: paramName } = shellLeagueContext(params?.leagueId ? decodeURIComponent(params.leagueId) : null, searchParams, UNNAMED_LEAGUE);
  const saved = useSavedLeagues(barVisible && Boolean(leagueId));

  useEffect(() => {
    if (!barVisible) return;
    let was = false;
    const onScroll = () => {
      const next = ribbonCollapsed(window.scrollY, was);
      if (next !== was) {
        was = next;
        setCollapsed(next);
      }
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [barVisible, pathname]);

  if (!barVisible) return null;
  const segment = (pathname || "").split("/").filter(Boolean)[0] ?? "";
  const title = segment ? PAGE_TITLE_BY_SEGMENT[segment] ?? "" : TERMS.yourLeagues;
  const parent = shellParent(pathname, { leagueId, leagueName: paramName });
  const template = headerTemplateFor(pathname);
  const showTitle = headerShowsTitle(pathname);
  const slots = headerSlotsFor(template);
  const resolvedName = (paramName && paramName !== UNNAMED_LEAGUE ? paramName : null) || saved.rows.find((r) => r.league_id === leagueId)?.league_name || null;
  const leagueName = resolvedName || "Your league";
  return (
    <header className="shell-header md:hidden" data-testid="shell-header" data-template={template} data-collapsed={collapsed ? "true" : "false"}>
      <div className="shell-header-row">
        {template !== "root" && parent ? (
          <Link href={parent.href} className="shell-header-back" aria-label={`Back to ${parent.label}`}>
            <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="m15 18-6-6 6-6" />
            </svg>
            <span className="truncate text-xs font-bold">{parent.label}</span>
          </Link>
        ) : null}
        {leagueId && template === "root" ? (
          <LeagueIdentity leagueId={leagueId} name={leagueName} onOpen={() => setSwitcherOpen(true)} />
        ) : template === "root" ? (
          <Link href="/" aria-label="FantasyDesk home" className="shell-header-brand">
            <Image src="/brand-mark.png" alt="" width={28} height={28} className="brand-mark-icon" style={{ objectFit: "contain" }} />
            <span className="text-sm font-extrabold uppercase" style={{ letterSpacing: "0.03em" }}>FantasyDesk</span>
          </Link>
        ) : (
          <>
            {!parent ? (
              <Link href="/" aria-label="FantasyDesk home" className="shell-header-back">
                <Image src="/brand-mark.png" alt="" width={26} height={26} className="brand-mark-icon" style={{ objectFit: "contain" }} />
              </Link>
            ) : null}
            <div className="flex min-w-0 flex-1 items-center">
              <h1 className="min-w-0 shrink break-words text-sm font-extrabold leading-tight" data-testid="shell-title">{title}</h1>
              <span id={SHELL_PAGE_INFO_SLOT_ID} className="inline-flex" />
            </div>
            {leagueId && slots.crest ? (
              <button type="button" onClick={() => { setSwitcherSeen(true); setSwitcherOpen(true); }} aria-label={`${leagueName}. Switch league`} aria-haspopup="dialog" className="shell-header-crest">
                <LeagueCrest leagueId={leagueId} name={leagueName} size={32} />
              </button>
            ) : null}
          </>
        )}
        {template === "root" ? (
          <>
            {/* The page's "?" explainer (PageTitle info) still has its slot; the h1 stays for the outline and screen readers. */}
            <span id={SHELL_PAGE_INFO_SLOT_ID} className="inline-flex" />
            {!showTitle && title ? <h1 className="sr-only" data-testid="shell-title">{title}</h1> : null}
          </>
        ) : null}
        {slots.actions ? <div className="flex shrink-0 items-center">{actions}</div> : null}
      </div>
      {template === "root" && chips.length > 0 ? <Ribbon chips={chips} /> : null}
      {leagueId && (switcherOpen || switcherSeen) ? <LeagueSwitcherSheet open={switcherOpen} onClose={() => setSwitcherOpen(false)} leagueId={leagueId} leagueName={leagueName} leagues={saved.rows} status={saved.status} onRetry={saved.reload} /> : null}
    </header>
  );
}

export function LeagueIdentity({ leagueId, name, onOpen }: { leagueId: string; name: string; onOpen: () => void }) {
  const { lens } = useValuationLens(leagueId);
  const lensLabel = VALUATION_LENS_OPTIONS.find((o) => o.value === lens)?.label ?? "Dynasty";
  return (
    <button type="button" onClick={onOpen} aria-haspopup="dialog" aria-label={`${name}, ${lensLabel} lens. Switch league`} className="shell-header-identity" data-testid="league-identity">
      <LeagueCrest leagueId={leagueId} name={name} size={32} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="shell-header-league break-words">{name}</span>
        <span className="text-[0.6875rem] font-bold leading-tight" style={{ color: "var(--color-text-muted)" }}>
          {lensLabel} lens ▾
        </span>
      </span>
    </button>
  );
}

function Ribbon({ chips }: { chips: HeaderChip[] }) {
  return (
    <div className="shell-header-ribbon" data-testid="header-ribbon" role="group" aria-label="This page at a glance">
      <div className="shell-header-ribbon-inner" tabIndex={0}>
        {chips.map((chip) => (
          <span key={chip.key} className="shell-header-chip" style={{ color: CHIP_COLOR[chip.tone ?? "muted"] }}>
            {chip.text}
          </span>
        ))}
      </div>
    </div>
  );
}
