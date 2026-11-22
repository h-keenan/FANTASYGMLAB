"use client";

import { Suspense, useEffect, useState } from "react";
import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { LoadingScreen } from "@/components/LoadingScreen";
import { SimGameContent } from "@/components/SimGameContent";
import { useAuth } from "@/context/AuthContext";
import { useSearchParams } from "@/lib/useSearchParams";

// Fantasy Sim: the GM Game. Like Portfolio it has no [leagueId] segment: it is
// a standalone game that lives in the General menu and never reads a league.
// Deep link: /gm-game?quickstart=1 opens a Quick game with no league connected
// (a signed-out visitor gets a disposable guest session first, like Connect).
function GmGameEntry() {
  const { session, loading, signInAsGuest } = useAuth();
  const quickStart = useSearchParams().get("quickstart") === "1";
  const [guest, setGuest] = useState<"idle" | "pending" | "failed">("idle");
  const needsGuest = quickStart && !loading && !session;
  useEffect(() => {
    if (!needsGuest || guest !== "idle") return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot guest sign-in on a quickstart deep link
    setGuest("pending");
    void signInAsGuest().then((r) => {
      if (r.error) setGuest("failed");
    });
  }, [needsGuest, guest, signInAsGuest]);
  if (loading || (needsGuest && guest !== "failed")) {
    return <LoadingScreen label="Fantasy Sim" layout="dashboard" />;
  }
  if (!session) {
    return (
      <main className="page-shell">
        <EmptyState title="Sign in to play Fantasy Sim" subtitle="Draft a team, play a season against AI managers and get graded. Your saves follow your account." centered>
          <ButtonLink href="/">Sign in</ButtonLink>
        </EmptyState>
      </main>
    );
  }
  return <SimGameContent quickStart={quickStart} />;
}

export default function GmGamePage() {
  return (
    <Suspense fallback={<LoadingScreen label="Fantasy Sim" layout="dashboard" />}>
      <GmGameEntry />
    </Suspense>
  );
}
