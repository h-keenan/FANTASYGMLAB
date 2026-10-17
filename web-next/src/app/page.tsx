"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { AgeGate } from "@/components/AgeGate";
import { LoadingScreen } from "@/components/LoadingScreen";
import { SleeperImportForm } from "@/components/SleeperImportForm";
import { SignInForm } from "@/components/SignInForm";
import { supabase } from "@/lib/supabase";

type Tab = "guest" | "account";

export default function LandingPage() {
  const { session, loading } = useAuth();
  const router = useRouter();
  // Defaults to the real sign-in/create-account path, not guest — coridian_,
  // 2026-10-17: "It defaults for you to sign in with a username from
  // sleeper, not an account." Guest (Sleeper-username-only, no account) is
  // still available as a secondary tab, just no longer the default.
  const [tab, setTab] = useState<Tab>("account");
  const [guestAgeConfirmed, setGuestAgeConfirmed] = useState(false);
  const [accountReady, setAccountReady] = useState(false);
  const [checkingSavedLeagues, setCheckingSavedLeagues] = useState(false);
  const skippedExistingSession = useRef(false);

  // A returning user (page refresh with a still-valid persisted Supabase
  // session — guest or signed-in) should land straight in their league, not
  // be asked to pass the age gate or sign in again, and not have to pick a
  // league back out of a list every time either (coridian_, 2026-10-17:
  // "the website needs to remember that you've signed in, and whenever you
  // open it, it needs to take you to the dashboard"). Mirrors mobile's own
  // HomeScreen auto-nav exactly: exactly one saved league jumps straight to
  // its Dashboard; two or more land on the cross-league Portfolio view
  // instead of guessing which one; zero saved leagues falls through to the
  // normal guest/account flow below. Only applies once, on load — never
  // re-triggers mid-flow.
  useEffect(() => {
    if (loading || !session || skippedExistingSession.current) return;
    skippedExistingSession.current = true;
    setGuestAgeConfirmed(true);
    setAccountReady(true);
    setCheckingSavedLeagues(true);
    (async () => {
      try {
        const { data } = await supabase.from("saved_leagues").select("league_id, league_name");
        const leagues = data ?? [];
        if (leagues.length === 1) {
          const only = leagues[0];
          router.replace(
            `/dashboard/${encodeURIComponent(only.league_id)}?name=${encodeURIComponent(only.league_name || only.league_id)}`,
          );
          return;
        }
        if (leagues.length > 1) {
          router.replace("/portfolio");
          return;
        }
        setCheckingSavedLeagues(false);
      } catch {
        setCheckingSavedLeagues(false);
      }
    })();
  }, [loading, session, router]);

  const handleLeagueChosen = (leagueId: string, leagueName: string) => {
    router.push(`/dashboard/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`);
  };

  if (loading || checkingSavedLeagues) {
    return <LoadingScreen />;
  }

  return (
    <main className="flex-1 flex flex-col items-center px-4 py-12 gap-10">
      {/* Hero / value prop — previously this page had none at all, nothing
          to tell a new visitor what the app even is (coridian_, 2026-10-17:
          "there is no clear representation as to what the app is"). Copy
          below is verbatim from mobile's onboarding carousel (coridian_-
          approved via Discord brainstorm, 2026-09-26 — "do not rephrase
          without re-checking with product"), not newly written here. */}
      <div className="w-full max-w-md flex flex-col gap-3 text-center">
        <h1 style={{ font: "var(--font-page-title)" }}>Your fantasy front office, not just a stats app.</h1>
        <p className="text-base" style={{ color: "var(--color-text-secondary)" }}>
          Real recommendations across your Trade Hub, Waivers, and Next Move — not raw data you have to interpret
          yourself.
        </p>
      </div>

      <div className="w-full max-w-sm flex flex-col gap-6">
        <div className="flex" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
          <button
            onClick={() => setTab("account")}
            className="flex-1 px-3 py-2 text-sm font-bold"
            style={{
              color: tab === "account" ? "var(--color-accent)" : "var(--color-text-muted)",
              borderBottom: tab === "account" ? "var(--border-width-semantic) solid var(--color-accent)" : "none",
            }}
          >
            Sign in / Create account
          </button>
          <button
            onClick={() => setTab("guest")}
            className="flex-1 px-3 py-2 text-sm font-bold"
            style={{
              color: tab === "guest" ? "var(--color-accent)" : "var(--color-text-muted)",
              borderBottom: tab === "guest" ? "var(--border-width-semantic) solid var(--color-accent)" : "none",
            }}
          >
            Try without an account
          </button>
        </div>

        {tab === "guest" ? (
          guestAgeConfirmed ? (
            <SleeperImportForm onLeagueChosen={handleLeagueChosen} />
          ) : (
            <AgeGate onConfirmed={() => setGuestAgeConfirmed(true)} />
          )
        ) : accountReady ? (
          <SleeperImportForm onLeagueChosen={handleLeagueChosen} />
        ) : (
          <SignInForm onSignedIn={() => setAccountReady(true)} />
        )}
      </div>
    </main>
  );
}
