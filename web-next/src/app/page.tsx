"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { AppStoreModules } from "@/components/AppStoreModules";
import { LoadingScreen } from "@/components/LoadingScreen";
import { OnboardingCarousel } from "@/components/OnboardingCarousel";
import { OnboardingPaywall } from "@/components/OnboardingPaywall";
import { SleeperImportForm } from "@/components/SleeperImportForm";
import { SignInForm } from "@/components/SignInForm";
import { trackFeatureUse } from "@/lib/analytics";
import { supabase } from "@/lib/supabase";

// useSearchParams() (for ?billing=success, see paywallDismissed below)
// requires a Suspense boundary around anything that calls it, or this
// page's otherwise-static prerender fails the build entirely — Next.js
// App Router's own documented requirement, not specific to this page.
export default function LandingPage() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <LandingPageContent />
    </Suspense>
  );
}

function LandingPageContent() {
  const { session, loading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [accountReady, setAccountReady] = useState(false);
  // Shown once per landing on this page — reset is irrelevant since this
  // flow (accountReady with no saved leagues yet) only ever happens for an
  // account that hasn't finished onboarding; once they have a saved league
  // the returning-session effect above redirects them away before any of
  // this renders again. Starts already-dismissed when returning from a
  // completed checkout (?billing=success) — OnboardingPaywall's own
  // checkout redirects back here, and showing the exact same trial offer
  // again to someone who just subscribed would be absurd.
  const [paywallDismissed, setPaywallDismissed] = useState(
    () => searchParams.get("billing") === "success",
  );
  // Same reasoning as paywallDismissed just above (and the same session-
  // only, not-persisted tradeoff that one already accepts) — the carousel
  // sits before the paywall in this flow, so returning from a completed
  // checkout means it was necessarily already seen or skipped this session.
  const [carouselDone, setCarouselDone] = useState(() => searchParams.get("billing") === "success");
  const [checkingSavedLeagues, setCheckingSavedLeagues] = useState(false);
  const skippedExistingSession = useRef(false);
  // Guards the one-time `landing_viewed` fire below -- see its own effect's
  // doc comment for why a plain `!loading && !checkingSavedLeagues` check
  // isn't safe here on its own.
  const welcomeViewTracked = useRef(false);
  // Distinguishes "the saved-leagues redirect check genuinely finished and
  // found nothing to redirect to" (safe to count as a real landing view)
  // from "checkingSavedLeagues just hasn't flipped true yet this tick"
  // (same false value, opposite meaning) -- see the effect below.
  const savedLeaguesCheck = useRef<"idle" | "pending" | "resolved">("idle");

  // A returning user (page refresh with a still-valid persisted Supabase
  // session) should land straight in their league, not be asked to sign in
  // again, and not have to pick a league back out of a list every time
  // either (coridian_, 2026-10-17: "the website needs to remember that
  // you've signed in, and whenever you open it, it needs to take you to
  // the dashboard"). Mirrors mobile's own HomeScreen auto-nav exactly:
  // exactly one saved league jumps straight to its Dashboard; two or more
  // land on the cross-league Portfolio view instead of guessing which one;
  // zero saved leagues falls through to the normal sign-in flow below.
  // Only applies once, on load — never re-triggers mid-flow.
  useEffect(() => {
    if (loading || !session || skippedExistingSession.current) return;
    skippedExistingSession.current = true;
    savedLeaguesCheck.current = "pending";
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
        savedLeaguesCheck.current = "resolved";
        setCheckingSavedLeagues(false);
      } catch (err) {
        // Previously silent — a failure here left zero trace anywhere,
        // the same invisible-failure gap found and fixed today in
        // services/stripe_webhook_service.py and
        // services/revenuecat_webhook_service.py. console.error at least
        // makes it visible in a browser's own dev tools during a future
        // repro, even without a telemetry pipeline wired up yet.
        console.error("Failed to load saved leagues after sign-in", err);
        savedLeaguesCheck.current = "resolved";
        setCheckingSavedLeagues(false);
      }
    })();
  }, [loading, session, router]);

  // Fires `landing_viewed` exactly once per visitor, only once we're sure
  // they're actually looking at the sign-in form / onboarding carousel /
  // paywall / Sleeper import form below -- never for a signed-in visitor
  // who's about to get auto-redirected straight to their Dashboard or
  // Portfolio by the effect above. The naive version of this check
  // (`!loading && !checkingSavedLeagues`) is NOT safe on its own: on the
  // very first render after a persisted session is found, this component
  // re-renders with `checkingSavedLeagues` still at its stale initial
  // `false` -- the effect above hasn't committed its own `setChecking
  // SavedLeagues(true)` yet, since that state update only lands on the
  // NEXT render, not this one. Without the `savedLeaguesCheck` ref, that
  // one-tick race would record a landing view for every returning user,
  // including ones who never actually see this page's content.
  useEffect(() => {
    if (welcomeViewTracked.current || loading) return;
    if (!session) {
      // No session at all: definitely rendering the sign-in form, not
      // redirecting anywhere.
      welcomeViewTracked.current = true;
      trackFeatureUse("landing_viewed", { props: { source_surface: "landing_hero" } });
      return;
    }
    // A session exists -- only count this as a real view once the saved-
    // leagues redirect check has actually run to completion and found
    // nothing to redirect to (`"resolved"`). Still `"idle"` or `"pending"`
    // means either the check hasn't started yet this tick, or it's still
    // in flight / about to redirect away -- never a real view either way.
    if (savedLeaguesCheck.current === "resolved" && !checkingSavedLeagues) {
      welcomeViewTracked.current = true;
      trackFeatureUse("landing_viewed", { props: { source_surface: "landing_hero" } });
    }
  }, [loading, session, checkingSavedLeagues]);

  const handleLeagueChosen = (leagueId: string, leagueName: string) => {
    router.push(`/dashboard/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`);
  };

  if (loading || checkingSavedLeagues) {
    return <LoadingScreen />;
  }

  return (
    <main className="fd-landing-dark flex-1 flex flex-col items-center px-4 py-12 gap-10">
      <div className="onboarding-field" aria-hidden="true" />
      <div className="onboarding-sweep" aria-hidden="true" />
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
        {/* coridian_, 2026-10-18: "we need to specify on the website that
            it's sleeper for the username and sleeper leagues right now
            until we get ESPN integration down, then we can differentiate"
            — a new addition here, not a rephrase of the hero copy above
            (that's approved, do-not-rephrase product copy). The actual
            field label/explanation already said "Sleeper" (onboarding
            audit, 2026-10-18), but nothing said so before reaching it. */}
        <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
          Works with your Sleeper league — ESPN support is on the way.
        </p>

        {accountReady ? (
          !carouselDone ? (
            <OnboardingCarousel onDone={() => setCarouselDone(true)} />
          ) : paywallDismissed ? (
            <SleeperImportForm onLeagueChosen={handleLeagueChosen} />
          ) : (
            <OnboardingPaywall onSkip={() => setPaywallDismissed(true)} />
          )
        ) : (
          <SignInForm onSignedIn={() => setAccountReady(true)} />
        )}
      </div>

      {/* Native app store slots, below the primary sign-in action so they
          never compete with it. Both apps are still "Coming soon" — see
          lib/appStoreLinks.ts for the one-line go-live switch. */}
      <AppStoreModules />
    </main>
  );
}
