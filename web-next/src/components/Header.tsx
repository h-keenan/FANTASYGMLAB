"use client";

import Image from "next/image";
import { OPEN_SEARCH_EVENT } from "@/lib/orbSearch";
import Link from "next/link";
import { usePathname, useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { Suspense, useEffect, useRef, useState } from "react";

import { AlertsBell } from "@/components/AlertsDropdown";
import { useAuth } from "@/context/AuthContext";
import { BRAND_NAME } from "@/lib/brand";
import { supabase } from "@/lib/supabase";
import { maskSavedLeagueRows } from "@/lib/privacy";
import { VALUATION_LENS_OPTIONS, useValuationLens } from "@/context/ValuationLensContext";
import { swapLeagueIdInPath } from "@/lib/leagueSwitcher";
import { PAGE_TITLE_BY_SEGMENT } from "@/lib/navDestinations";

const LEGAL_LINKS: { pageKey: string; label: string }[] = [
  { pageKey: "about_disclaimer", label: "About / Disclaimer" },
  { pageKey: "terms", label: "Terms of Use" },
  { pageKey: "privacy", label: "Privacy Policy" },
  { pageKey: "subscription_terms", label: "Subscription Terms" },
  { pageKey: "no_affiliation", label: "No-Affiliation Disclaimer" },
];

export interface SavedLeagueRow {
  league_id: string;
  league_name: string | null;
}

export function LeagueSwitcherButton({
  leagueId,
  leagueName,
  leagues,
}: {
  leagueId: string;
  leagueName: string | null;
  leagues: SavedLeagueRow[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="px-2.5 py-2.5 text-xs font-bold max-w-[9rem] truncate min-h-[var(--touch-target-min)]"
        style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
      >
        {/* coridian_, 2026-10-18: "where it says dashboard and revivalary...
            revival should go to the league switcher so that... you can
            always see what league you're on in the header." The button
            itself now names the current league instead of a generic
            "Switch league" label — the league-name span this replaced was
            hidden below sm width anyway, so mobile never showed it at all. */}
        {leagueName || "Switch league"} ▾
      </button>
      {open ? (
        <>
          <button type="button" aria-hidden tabIndex={-1} className="fixed inset-0" style={{ background: "transparent", zIndex: 40 }} onClick={() => setOpen(false)} />
          {/* left-0, not right-0 — this button sits near the header's left
              edge (it's the first of the league controls), so a right-0
              anchored w-56 menu had nowhere to grow but off the left edge
              of the viewport (coridian_, 2026-10-18, screenshot: "Switch
              league button clips off screen"). left-0 keeps it growing
              rightward into the header's own open space instead. */}
          <div role="menu" className="glass-surface absolute left-0 top-full mt-1 flex flex-col py-1 w-56" style={{ zIndex: 50, maxWidth: "calc(100vw - 2rem)" }}>
            {leagues.length === 0 ? (
              <span className="px-3 py-3 text-xs" style={{ color: "var(--color-text-muted)" }}>
                No other saved leagues
              </span>
            ) : (
              leagues.map((row) => (
                <button
                  key={row.league_id}
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpen(false);
                    const newPath = swapLeagueIdInPath(pathname || "", leagueId, row.league_id);
                    router.push(`${newPath}?name=${encodeURIComponent(row.league_name || row.league_id)}`);
                  }}
                  className="px-3 py-3 text-xs font-semibold text-left"
                  style={{ color: row.league_id === leagueId ? "var(--color-accent)" : "var(--color-text-secondary)" }}
                >
                  {row.league_name || row.league_id}
                </button>
              ))
            )}
            {/* coridian_, screenshot of this exact menu: "how do i add
                leauges" — there was no way to, once already past
                onboarding ("/" auto-redirects anyone with a saved league
                away before SleeperImportForm ever renders again). */}
            <Link
              href="/connect-league"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="px-3 py-3 text-xs font-bold text-left"
              style={{ color: "var(--color-accent)", borderTop: "var(--border-width-default) solid var(--color-border)" }}
            >
              + Add another league
            </Link>
          </div>
        </>
      ) : null}
    </div>
  );
}

const LENS_PANEL_WIDTH_PX = 256; // w-64

/**
 * Neither a static `left-0` nor a static `right-0` is correct for this
 * button in every layout: on most viewports the header's right-hand
 * control cluster sits flush against the right edge (so the panel must
 * grow leftward, `right-0`, or it clips off the right side of the screen —
 * coridian_ screenshot), but on a narrow phone the header row can wrap and
 * leave this button alone near the LEFT edge instead (the exact case
 * e95fc345 fixed by switching to `left-0` — a static swap back to `right-0`
 * would silently reintroduce that regression). Measuring the button's real
 * position and picking whichever anchor keeps the panel on-screen is the
 * only choice that's correct in both layouts.
 */
function chooseDropdownAnchor(buttonLeft: number, buttonRight: number, viewportWidth: number): "left-0" | "right-0" {
  const spaceRight = viewportWidth - buttonLeft;
  const spaceLeft = buttonRight;
  if (spaceRight >= LENS_PANEL_WIDTH_PX) return "left-0";
  if (spaceLeft >= LENS_PANEL_WIDTH_PX) return "right-0";
  // Neither side fully fits — pick whichever has more room; the
  // `maxWidth: calc(100vw - 2rem)` clamp below keeps it from overflowing.
  return spaceRight >= spaceLeft ? "left-0" : "right-0";
}

export function EvaluationLensButton({ leagueId }: { leagueId: string }) {
  const { lens, setLens } = useValuationLens(leagueId);
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<"left-0" | "right-0">("right-0");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const current = VALUATION_LENS_OPTIONS.find((option) => option.value === lens);

  function toggleOpen() {
    setOpen((value) => {
      const next = !value;
      if (next && buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect();
        setAnchor(chooseDropdownAnchor(rect.left, rect.right, window.innerWidth));
      }
      return next;
    });
  }

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={toggleOpen}
        aria-expanded={open}
        aria-haspopup="menu"
        className="px-2.5 py-2.5 text-xs font-bold min-h-[var(--touch-target-min)]"
        style={{ color: "var(--color-premium)", border: "var(--border-width-default) solid var(--color-premium)" }}
      >
        {current?.label ?? "Dynasty"} ▾
      </button>
      {open ? (
        <>
          <button type="button" aria-hidden tabIndex={-1} className="fixed inset-0" style={{ background: "transparent", zIndex: 40 }} onClick={() => setOpen(false)} />
          <div
            role="menu"
            className={`glass-surface absolute ${anchor} top-full mt-1 flex flex-col py-1 w-64`}
            style={{ zIndex: 50, maxWidth: "calc(100vw - 2rem)" }}
          >
            {VALUATION_LENS_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                role="menuitem"
                onClick={() => {
                  setLens(option.value);
                  setOpen(false);
                }}
                className="flex flex-col px-3 py-2 text-left"
                style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
              >
                <span className="text-xs font-bold" style={{ color: option.value === lens ? "var(--color-premium)" : "var(--color-text-primary)" }}>
                  {option.label}
                </span>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {option.hint}
                </span>
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

/**
 * The league-aware pieces of the header (switcher/lens/league-name) —
 * split out specifically so useParams/useSearchParams (which force Next.js
 * to render this subtree dynamically, client-side-only) don't hold back
 * the rest of the header too. Before this split, the ENTIRE header needed
 * a Suspense boundary around it just for this, which meant the brand
 * mark/wordmark — content every single page needs, league-scoped or not —
 * had nothing in the server-rendered HTML either, a blank gap until
 * hydration (new-user UX audit finding, 2026-10-17). Only this smaller
 * piece needs the Suspense wrap now; the rest of Header renders
 * synchronously on every page.
 */
function HeaderLeagueControls() {
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  const nameParam = searchParams.get("name");
  const [savedLeagues, setSavedLeagues] = useState<SavedLeagueRow[]>([]);

  // Fetches the user's saved leagues once per league-scoped page (not just
  // lazily when the switcher dropdown opens, like before) so the header's
  // own displayed name can resolve `leagueId` -> real league name from
  // `saved_leagues` whenever a caller forgot to pass `?name=` on its link —
  // the raw-league_id-in-the-header bug (coridian_ screenshot) was exactly
  // that: `leagueName` had no fallback besides the URL query param. This
  // also means LeagueSwitcherButton's dropdown list is ready the instant
  // it's opened instead of flashing "No other saved leagues" first.
  useEffect(() => {
    if (!leagueId) return;
    let cancelled = false;
    supabase
      .from("saved_leagues")
      .select("league_id, league_name")
      .then(({ data }) => {
        if (!cancelled) setSavedLeagues(maskSavedLeagueRows(data ?? []));
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (!leagueId) return null;

  const resolvedName = nameParam || savedLeagues.find((row) => row.league_id === leagueId)?.league_name || null;
  const leagueName = resolvedName || leagueId;

  return (
    <>
      <LeagueSwitcherButton leagueId={leagueId} leagueName={leagueName} leagues={savedLeagues} />
      <EvaluationLensButton leagueId={leagueId} />
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
function HeaderPageTitle() {
  const pathname = usePathname();
  const segment = (pathname || "").split("/").filter(Boolean)[0] || "";
  const title = PAGE_TITLE_BY_SEGMENT[segment];
  if (!title) return null;
  return (
    <span className="text-xs font-bold uppercase break-words leading-tight" style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}>
      {title}
    </span>
  );
}

const ICON_BUTTON_STYLE = {
  color: "var(--color-text-secondary)",
  border: "var(--border-width-default) solid var(--color-border)",
  borderRadius: "var(--radius-control)",
  width: "2.5rem",
  height: "2.5rem",
} as const;

/**
 * Search and alerts, level with the page title. Search opens the GM orb's
 * destination and player search (no second search UI); the bell opens an
 * alerts dropdown (AlertsDropdown.tsx) that links to the Alerts page. Alerts only exists inside a league, so the bell is
 * hidden elsewhere. Rendered only when signed in.
 */
function HeaderIconActions() {
  const { session } = useAuth();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  const leagueId = params?.leagueId ? decodeURIComponent(params.leagueId) : null;
  if (!session) return null;
  const name = searchParams.get("name");
  const alertsHref = leagueId
    ? `/alerts/${encodeURIComponent(leagueId)}${name ? `?name=${encodeURIComponent(name)}` : ""}`
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
 * `/portfolio`/`/news`/etc. there is no league context for either to act
 * on. Real branding (2026-10-17: "The header also needs the branding") is
 * the same brand mark mobile's splash/loading screen and GM orb use
 * (public/brand-mark.png, copied from mobile/assets/splash-icon.png) — not
 * invented fresh here.
 */
export function Header() {
  const { session, signOut } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header
      className="flex flex-col px-4 py-3 relative gap-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        <Link href="/" className="flex items-center gap-2 p-2 -m-2">
          <Image src="/brand-mark.png" alt="" width={28} height={28} className="brand-mark-icon" style={{ objectFit: "contain" }} />
          <span className="hidden sm:inline text-sm font-extrabold uppercase" style={{ color: "var(--color-text-primary)", letterSpacing: "0.03em" }}>
            {BRAND_NAME}
          </span>
        </Link>
        <HeaderPageTitle />
      </div>

      <div className="flex items-center gap-2">
        <Suspense fallback={null}>
          <HeaderIconActions />
        </Suspense>

        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="px-3 py-2.5 text-xs font-bold uppercase min-h-[var(--touch-target-min)]"
            style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)", letterSpacing: "0.03em" }}
          >
            Menu
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
                    Account
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
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      void signOut().then(() => router.replace("/"));
                    }}
                    className="px-3 py-3 text-xs font-semibold text-left"
                    style={{ color: "var(--color-danger)", borderTop: "var(--border-width-default) solid var(--color-border)" }}
                  >
                    Sign out
                  </button>
                ) : null}
              </div>
            </>
          ) : null}
        </div>
      </div>
      </div>
      <div className="flex items-center gap-2 flex-wrap empty:hidden">
        <Suspense fallback={null}>
          <HeaderLeagueControls />
        </Suspense>
      </div>
    </header>
  );
}
