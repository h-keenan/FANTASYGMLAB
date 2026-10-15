"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { AgeGate } from "@/components/AgeGate";
import { SleeperImportForm } from "@/components/SleeperImportForm";
import { SignInForm } from "@/components/SignInForm";

type Tab = "guest" | "account";

export default function LandingPage() {
  const { session, loading } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("guest");
  const [guestAgeConfirmed, setGuestAgeConfirmed] = useState(false);
  const [accountReady, setAccountReady] = useState(false);
  const skippedExistingSession = useRef(false);

  // A returning user (page refresh with a still-valid persisted Supabase
  // session — guest or signed-in) should land straight on the league
  // picker, not be asked to pass the age gate or sign in again. Only
  // applies once, on load — never re-triggers mid-flow.
  useEffect(() => {
    if (!loading && session && !skippedExistingSession.current) {
      skippedExistingSession.current = true;
      setGuestAgeConfirmed(true);
      setAccountReady(true);
    }
  }, [loading, session]);

  const handleLeagueChosen = (leagueId: string, leagueName: string) => {
    router.push(`/dashboard/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`);
  };

  if (loading) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p style={{ color: "var(--color-text-muted)" }}>Loading…</p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm flex flex-col gap-6">
        <div className="flex flex-col gap-1 text-center">
          <h1 style={{ font: "var(--font-page-title)" }}>FantasyGM Lab</h1>
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            Your dynasty fantasy football GM assistant.
          </p>
        </div>

        <div className="flex" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
          <button
            onClick={() => setTab("guest")}
            className="flex-1 px-3 py-2 text-sm font-bold"
            style={{
              color: tab === "guest" ? "var(--color-accent)" : "var(--color-text-muted)",
              borderBottom: tab === "guest" ? "var(--border-width-semantic) solid var(--color-accent)" : "none",
            }}
          >
            Continue as guest
          </button>
          <button
            onClick={() => setTab("account")}
            className="flex-1 px-3 py-2 text-sm font-bold"
            style={{
              color: tab === "account" ? "var(--color-accent)" : "var(--color-text-muted)",
              borderBottom: tab === "account" ? "var(--border-width-semantic) solid var(--color-accent)" : "none",
            }}
          >
            Sign in
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
