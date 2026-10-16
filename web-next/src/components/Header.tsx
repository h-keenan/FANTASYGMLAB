"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/context/AuthContext";

const LEGAL_LINKS: { pageKey: string; label: string }[] = [
  { pageKey: "about_disclaimer", label: "About / Disclaimer" },
  { pageKey: "terms", label: "Terms of Use" },
  { pageKey: "privacy", label: "Privacy Policy" },
  { pageKey: "subscription_terms", label: "Subscription Terms" },
  { pageKey: "no_affiliation", label: "No-Affiliation Disclaimer" },
];

/**
 * Site-wide persistent top bar — rendered once in layout.tsx, so every
 * route gets it for free (coridian_: "add ... the header", 2026-10-16).
 * This app had no persistent nav/header at all before this: every route
 * was reachable only via Dashboard's own in-page "Explore" links or a
 * direct URL, and the 5 legal pages (see src/app/legal/[pageKey]) had no
 * entry point whatsoever. Kept deliberately small — a brand/home link plus
 * a menu for the genuinely-orphaned destinations (legal pages, sign out) —
 * rather than flattening all ~20 content pages into one global nav, which
 * mobile itself doesn't do either (RootNavigator is a Dashboard-first
 * drill-down, not a flat tab bar; see MoreScreen.tsx for the same
 * legal-links-plus-account grouping this menu mirrors).
 */
export function Header() {
  const { session, signOut } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header
      className="flex items-center justify-between px-4 py-3 relative"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <Link href="/" className="text-sm font-extrabold uppercase" style={{ color: "var(--color-text-primary)", letterSpacing: "0.03em" }}>
        FantasyGM Lab
      </Link>

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
    </header>
  );
}
