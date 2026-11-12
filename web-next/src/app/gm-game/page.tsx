"use client";

import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { LoadingScreen } from "@/components/LoadingScreen";
import { SimGameContent } from "@/components/SimGameContent";
import { useAuth } from "@/context/AuthContext";

// Fantasy Sim: the GM Game. Like Portfolio it has no [leagueId] segment: it is
// a standalone game that lives in the General menu and never reads a league.
export default function GmGamePage() {
  const { session, loading } = useAuth();
  if (loading) return <LoadingScreen status="Loading Fantasy Sim…" />;
  if (!session) {
    return (
      <main className="flex-1 flex flex-col gap-3 px-4 py-6 max-w-3xl w-full mx-auto">
        <EmptyState title="Sign in to play Fantasy Sim" subtitle="Draft a team, play a season against AI managers and get graded. Your saves follow your account." centered>
          <ButtonLink href="/">Sign in</ButtonLink>
        </EmptyState>
      </main>
    );
  }
  return <SimGameContent />;
}
