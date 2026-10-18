"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { BRAND_NAME } from "@/lib/brand";
import { supabase } from "@/lib/supabase";
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

interface SavedLeagueRow {
  league_id: string;
  league_name: string | null;
}

function LeagueSwitcherButton({ leagueId, leagueName }: { leagueId: string; leagueName: string | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [leagues, setLeagues] = useState<SavedLeagueRow[]>([]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    supabase
      .from("saved_leagues")
      .select("league_id, league_name")
      .then(({ data }) => {
        if (!cancelled) setLeagues(data ?? []);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="px-2.5 py-1.5 text-xs font-bold max-w-[9rem] truncate"
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
          <div role="menu" className="absolute left-0 top-full mt-1 flex flex-col py-1 w-56" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)", zIndex: 50, maxWidth: "calc(100vw - 2rem)" }}>
            {leagues.length === 0 ? (
              <span className="px-3 py-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
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
                  className="px-3 py-2 text-xs font-semibold text-left"
                  style={{ color: row.league_id === leagueId ? "var(--color-accent)" : "var(--color-text-secondary)" }}
                >
                  {row.league_name || row.league_id}
                </button>
              ))
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

function EvaluationLensButton({ leagueId }: { leagueId: string }) {
  const { lens, setLens } = useValuationLens(leagueId);
  const [open, setOpen] = useState(false);
  const current = VALUATION_LENS_OPTIONS.find((option) => option.value === lens);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="px-2.5 py-1.5 text-xs font-bold"
        style={{ color: "var(--color-premium)", border: "var(--border-width-default) solid var(--color-premium)" }}
      >
        {current?.label ?? "Dynasty"} ▾
      </button>
      {open ? (
        <>
          <button type="button" aria-hidden tabIndex={-1} className="fixed inset-0" style={{ background: "transparent", zIndex: 40 }} onClick={() => setOpen(false)} />
          <div role="menu" className="absolute right-0 top-full mt-1 flex flex-col py-1 w-64" style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)", zIndex: 50, maxWidth: "calc(100vw - 2rem)" }}>
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
  const leagueName = searchParams.get("name") || leagueId;

  if (!leagueId) return null;

  return (
    <>
      <LeagueSwitcherButton leagueId={leagueId} leagueName={leagueName} />
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
    <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}>
      {title}
    </span>
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
      className="flex items-center justify-between px-4 py-3 relative gap-3 flex-wrap"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <div className="flex items-center gap-3 flex-wrap">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/brand-mark.png" alt="" width={28} height={28} style={{ objectFit: "contain" }} />
          <span className="text-sm font-extrabold uppercase" style={{ color: "var(--color-text-primary)", letterSpacing: "0.03em" }}>
            {BRAND_NAME}
          </span>
        </Link>
        <HeaderPageTitle />
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <Suspense fallback={null}>
          <HeaderLeagueControls />
        </Suspense>

        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            className="px-3 py-1.5 text-xs font-bold uppercase"
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
                className="absolute right-0 top-full mt-1 flex flex-col py-1 min-w-[12rem]"
                style={{
                  background: "var(--color-surface-secondary)",
                  border: "var(--border-width-default) solid var(--color-border)",
                  zIndex: 50,
                }}
              >
                {LEGAL_LINKS.map((item) => (
                  <Link
                    key={item.pageKey}
                    href={`/legal/${item.pageKey}`}
                    role="menuitem"
                    onClick={() => setMenuOpen(false)}
                    className="px-3 py-2 text-xs font-semibold"
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
                    className="px-3 py-2 text-xs font-semibold text-left"
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
    </header>
  );
}
