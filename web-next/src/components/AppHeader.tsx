"use client";

import Image from "next/image";
import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import Link from "next/link";
import { usePathname, useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { Suspense, useState } from "react";

import { AlertsBell } from "@/components/AlertsDropdown";
import { useAuth } from "@/context/AuthContext";
import { BRAND_NAME } from "@/lib/brand";
import { PAGE_TITLE_BY_SEGMENT } from "@/lib/navDestinations";
import { PAGE_INFO_SLOT_ID } from "@/components/PageTitle";
import { ConfirmInPlace } from "@/components/ui/ConfirmInPlace";
import { pathOwnsPhoneChrome } from "@/lib/bottomNav";
import { LeagueIdentity, LeagueSwitcherSheet, ShellHeader } from "@/components/ShellHeader";
import { headerSlotsFor, headerTemplateFor, headerTitleFor } from "@/lib/appHeader";
import { useShellNav } from "@/lib/useShellNav";
import { useSavedLeagues } from "@/lib/useSavedLeagues";

const LEGAL_LINKS: { pageKey: string; label: string }[] = [
  { pageKey: "about_disclaimer", label: "About / Disclaimer" },
  { pageKey: "terms", label: "Terms of Use" },
  { pageKey: "privacy", label: "Privacy Policy" },
  { pageKey: "subscription_terms", label: "Subscription Terms" },
  { pageKey: "no_affiliation", label: "No-Affiliation Disclaimer" },
];


/**
 * League identity on the wide / signed-out bar: the SAME crest + name + lens button and switcher sheet the phone shell uses
 * (ShellHeader's LeagueIdentity + LeagueSwitcherSheet). The old dropdown pickers (LeagueSwitcherButton, LeagueLensPicker,
 * EvaluationLensButton) are retired; the switcher sheet carries the league list, "Connect a league" and the lens.
 */
function WideLeagueControls() {
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  const { barVisible } = useShellNav();
  // The phone shell fetches the list itself (ShellHeader); this bar only needs it when the shell is off.
  const saved = useSavedLeagues(Boolean(leagueId) && !barVisible);
  const [open, setOpen] = useState(false);
  const [seen, setSeen] = useState(false);
  if (!leagueId) return null;
  const leagueName = searchParams.get("name") || saved.rows.find((row) => row.league_id === leagueId)?.league_name || "Your league";
  return (
    <>
      <div className="min-w-0 max-w-[60%]">
        <LeagueIdentity leagueId={leagueId} name={leagueName} onOpen={() => { setSeen(true); setOpen(true); }} />
      </div>
      {seen || open ? <LeagueSwitcherSheet open={open} onClose={() => setOpen(false)} leagueId={leagueId} leagueName={leagueName} leagues={saved.rows} status={saved.status} onRetry={saved.reload} /> : null}
    </>
  );
}

/**
 * coridian_, 2026-10-18: "where it says dashboard and revivalary... I
 * think dashboard should go up into the header... so you can always see
 * what page you're on." Was only ever shown as a page-content <h1>-
 * adjacent label (e.g. DashboardContent.tsx's own "Dashboard" span),
 * which scrolls away with the rest of the page on a long screen. Derives
 * the label from the pathname's first segment against the same
 * destination list the GM orb/sidebar nav already use (PAGE_TITLE_BY_SEGMENT
 * in navDestinations.ts) rather than a second hand-maintained list, so this
 * needs no per-page wiring — it's already correct for every route today
 * and for any future one that reuses an existing path segment.
 */
/** Titles for signed-out public routes that are not league destinations (phone header has no wordmark room). */
const PUBLIC_PAGE_TITLE_BY_SEGMENT: Record<string, string> = {
  "sample-league": "Sample league",
  methodology: "Methodology",
  "dynasty-tools": "Dynasty tools",
  "dynasty-rankings": "Rankings",
  "dynasty-trade-value-chart": "Trade values",
};

function HeaderPageTitle() {
  const pathname = usePathname();
  const segment = (pathname || "").split("/").filter(Boolean)[0] || "";
  const title = PAGE_TITLE_BY_SEGMENT[segment];
  const template = headerTemplateFor(pathname);
  if (!title) {
    // Public pages (no league nav destination) still say where you are, compactly; they own their own <h1>.
    const publicTitle = PUBLIC_PAGE_TITLE_BY_SEGMENT[segment];
    if (!publicTitle || template === "immersive") return null;
    return (
      <span className="flex items-center min-w-0 text-xs font-bold uppercase leading-tight break-words" style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }} data-testid="header-public-title">
        {publicTitle}
      </span>
    );
  }
  // Rule 1 (lib/appHeader.ts): the sidebar / pill names a tab page, so only a page nothing else names shows a visible title; the h1 stays
  // for the outline and screen readers (axe page-has-heading-one). Immersive pages own their heading.
  const visible = template !== "immersive" && headerSlotsFor(template).title && headerTitleFor(title) !== "";
  return (
    <span className="flex items-center min-w-0">
      <h1 className={visible ? "text-xs font-bold uppercase leading-tight min-w-0 break-words" : "sr-only"} style={visible ? { color: "var(--color-text-muted)", letterSpacing: "0.03em" } : undefined}>
        {title}
      </h1>
      {/* Pages portal their "?" explainer here (PageTitle `info`). */}
      <span id={PAGE_INFO_SLOT_ID} className="inline-flex" />
    </span>
  );
}

const ICON_BUTTON_STYLE = {
  color: "var(--color-text-secondary)",
  border: "var(--border-width-default) solid var(--color-border)",
  borderRadius: "var(--radius-control)",
  width: "var(--touch-target-min)",
  height: "var(--touch-target-min)",
} as const;

/**
 * Search and alerts, level with the page title. Search opens the GM orb's
 * destination and player search (no second search UI); the bell opens an
 * alerts dropdown (AlertsDropdown.tsx) that links to the Alerts section of Today. Alerts only exists inside a league, so the bell is
 * hidden elsewhere. Rendered only when signed in.
 */
export function HeaderIconActions() {
  const { session } = useAuth();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  if (!session) return null;
  const name = searchParams.get("name");
  const alertsHref = leagueId
    ? `/dashboard/${encodeURIComponent(leagueId)}${name ? `?name=${encodeURIComponent(name)}` : ""}#alerts`
    : null;
  const svg = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  return (
    <>
      <button
        type="button"
        aria-label="Search players and pages"
        onClick={() => window.dispatchEvent(new Event(OPEN_SEARCH_EVENT))}
        className="inline-flex items-center justify-center"
        style={ICON_BUTTON_STYLE}
      >
        <svg {...svg}>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      </button>
      {alertsHref && leagueId ? (
        <AlertsBell key={leagueId} leagueId={leagueId} alertsHref={alertsHref} iconProps={svg} buttonStyle={ICON_BUTTON_STYLE} />
      ) : null}
    </>
  );
}

/**
 * Site-wide persistent top bar — rendered once in layout.tsx, so every
 * route gets it for free (coridian_: "add ... the header", 2026-10-16).
 * League switcher + evaluation lens (2026-10-17: "The header needs to have
 * a league switcher built into it, as well as the evaluation lens similar
 * to how the app is") only render on a league-scoped route — on `/` or
 * `/leagues`/`/news`/etc. there is no league context for either to act
 * on. Real branding (2026-10-17: "The header also needs the branding") is
 * the same brand mark mobile's splash/loading screen and GM orb use
 * (public/brand-mark.png, copied from mobile/assets/splash-icon.png) — not
 * invented fresh here.
 */
export function AppHeader() {
  const { session, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  // Pages with their own phone header + bottom bar (the Fantasy Sim game) hide this one below 768px.
  const ownChrome = Boolean(session) && pathOwnsPhoneChrome(pathname);
  // Phone shell flag (Phase B): the standard ShellHeader replaces this row below 768px.
  const { barVisible } = useShellNav();
  // Immersive pages (landing, onboarding, paywall, connect, live draft) get the minimal bar: brand + account, no league identity / search / bell.
  const slots = headerSlotsFor(headerTemplateFor(pathname));
  const minimal = !slots.identity && !slots.actions;

  return (
    <>
    {barVisible ? (
      <Suspense fallback={null}>
        <ShellHeader actions={<HeaderIconActions />} />
      </Suspense>
    ) : null}
    <header
      className={`flex flex-col px-2 py-0.5 relative${ownChrome || barVisible ? " max-md:hidden" : ""}`}
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-1">
      <div className="flex items-center min-w-0">
        <Link href="/" className="flex items-center gap-2 p-2 -m-2 mr-0 shrink-0" aria-label={`${BRAND_NAME} home`}>
          <Image src="/brand-mark.png" alt="" width={28} height={28} className="brand-mark-icon" style={{ objectFit: "contain" }} />
          <span className="hidden sm:inline text-sm font-extrabold uppercase" style={{ color: "var(--color-text-primary)", letterSpacing: "0.03em" }}>
            {BRAND_NAME}
          </span>
        </Link>
        <HeaderPageTitle />
      </div>

      {minimal ? null : (
        <Suspense fallback={null}>
          <WideLeagueControls />
        </Suspense>
      )}

      <div className="flex items-center shrink-0">
        {minimal ? null : (
          <Suspense fallback={null}>
            <HeaderIconActions />
          </Suspense>
        )}

        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            aria-label="Account"
            className="inline-flex items-center justify-center"
            style={ICON_BUTTON_STYLE}
          >
            <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <circle cx="12" cy="8" r="4" />
              <path d="M4 21c0-4 3.5-7 8-7s8 3 8 7" />
            </svg>
          </button>

          {menuOpen ? (
            <>
              {/* Full-viewport click-catcher to close on outside click —
                  simpler and more robust than a document-level listener for
                  a menu this small. */}
              <button
                type="button"
                aria-hidden
                tabIndex={-1}
                className="fixed inset-0"
                style={{ background: "transparent", zIndex: 40 }}
                onClick={() => setMenuOpen(false)}
              />
              <div
                role="menu"
                className="glass-surface absolute right-0 top-full mt-1 flex flex-col py-1 min-w-[12rem]"
                style={{
                  zIndex: 50,
                  // This button is always the last header item, so right-0
                  // is correct (nothing clips today), but clamping width is
                  // a cheap safety net consistent with the other two header
                  // menus' fix, for the "audit all of the menus" ask.
                  maxWidth: "calc(100vw - 2rem)",
                }}
              >
                <Link
                  href="/methodology"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                  className="px-3 py-3 text-xs font-semibold"
                  style={{ color: "var(--color-text-secondary)" }}
                >
                  How We Evaluate
                </Link>
                {session ? (
                  // Account/Settings (coridian_, 2026-10-19) — account
                  // chrome, not a feature page, so it lives in this Menu
                  // dropdown next to the legal links rather than in
                  // navDestinations.ts's GM orb/sidebar nav list.
                  <Link
                    href="/account"
                    role="menuitem"
                    onClick={() => setMenuOpen(false)}
                    className="px-3 py-3 text-xs font-semibold"
                    style={{ color: "var(--color-text-secondary)", borderTop: "var(--border-width-default) solid var(--color-border)" }}
                  >
                    Account settings
                  </Link>
                ) : null}
                {LEGAL_LINKS.map((item) => (
                  <Link
                    key={item.pageKey}
                    href={`/legal/${item.pageKey}`}
                    role="menuitem"
                    onClick={() => setMenuOpen(false)}
                    className="px-3 py-3 text-xs font-semibold"
                    style={{ color: "var(--color-text-secondary)" }}
                  >
                    {item.label}
                  </Link>
                ))}
                {session ? (
                  <ConfirmInPlace
                    plain
                    variant="row"
                    mode="tap-again"
                    label="Sign out"
                    triggerRole="menuitem"
                    triggerClassName="px-3 py-3 text-xs font-semibold text-left w-full"
                    triggerStyle={{ color: "var(--color-danger)", borderTop: "var(--border-width-default) solid var(--color-border)", background: "transparent", cursor: "pointer" }}
                    className="w-full"
                    onConfirm={async () => {
                      await signOut();
                      setMenuOpen(false);
                      router.replace("/");
                    }}
                  />
                ) : null}
              </div>
            </>
          ) : null}
        </div>
      </div>
      </div>
    </header>
    </>
  );
}
