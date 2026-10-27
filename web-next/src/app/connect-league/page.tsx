"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/context/AuthContext";
import { FreeLeagueLimitNote } from "@/components/FreeLeagueLimitNote";
import { LoadingScreen } from "@/components/LoadingScreen";
import { SampleLeagueButton } from "@/components/SampleLeagueBanner";
import { SleeperImportForm } from "@/components/SleeperImportForm";
import { pathAfterLeagueChosen } from "@/lib/tradeBridge";
import { storeCurrentPathForReturnAfterSignIn } from "@/lib/protectedRouteReturn";

// coridian_, screenshot of the league switcher: "how do i add leauges" —
// SleeperImportForm (the real "load my Sleeper leagues, pick one, save it"
// flow) already existed and already supports adding a league on top of
// ones a signed-in user already has (api.saveLeague is additive, not a
// replace — Header.tsx's LeagueSwitcherButton lists every saved_leagues
// row). It just had no route of its own once a user was already past
// onboarding: "/" auto-redirects anyone with 1+ saved leagues straight to
// their Dashboard/Portfolio before this form ever renders again. This page
// is that missing route, linked from the league switcher's new "+ Add
// another league" row.
export default function ConnectLeaguePage() {
  const router = useRouter();
  const { session, loading } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (!session) {
      // P0 UX audit, 2026-10-27: this used to silently drop a signed-out
      // visitor on "/" with no way back to this page once they signed in.
      // "/" is itself a reasonable destination (it's the real sign-in/
      // signup surface), so it stays the redirect target -- only the
      // missing return path is the bug. Consumed by LandingAuthIsland's
      // existing-saved-leagues branch (an account that's already past
      // onboarding), never by a brand-new signup still going through the
      // carousel/paywall -- see protectedRouteReturn.ts's own comment.
      storeCurrentPathForReturnAfterSignIn();
      router.replace("/");
    }
  }, [loading, session, router]);

  if (loading || !session) {
    return <LoadingScreen />;
  }

  return (
    <main className="flex-1 flex flex-col items-center px-4 py-12 gap-6">
      <div className="w-full max-w-sm flex flex-col gap-1 text-center">
        <h1 style={{ font: "var(--font-page-title)" }}>Add a league</h1>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Add a Sleeper, ESPN, Fleaflicker or MFL league alongside the leagues you already have.
        </p>
      </div>
      <div className="w-full max-w-sm flex flex-col gap-3">
        <FreeLeagueLimitNote />
        <SleeperImportForm onLeagueChosen={(leagueId, leagueName) => router.push(pathAfterLeagueChosen(leagueId, leagueName))} />
        <SampleLeagueButton surface="connect_step" />
      </div>
    </main>
  );
}
