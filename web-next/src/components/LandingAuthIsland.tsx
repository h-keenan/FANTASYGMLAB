"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { OnboardingCarousel } from "@/components/OnboardingCarousel";
import { OnboardingPaywall } from "@/components/OnboardingPaywall";
import { SleeperImportForm } from "@/components/SleeperImportForm";
import { SignInForm } from "@/components/SignInForm";
import { trackFeatureUse } from "@/lib/analytics";
import { setLandingPending } from "@/lib/landingPending";
import { supabase } from "@/lib/supabase";

/**
 * Reserves the sign-in card's slot while auth is still resolving (and as
 * this island's Suspense fallback during static prerender), so the
 * server-rendered hero/app-store content around it doesn't jump when the
 * real form arrives. Deliberately has no "Loading…" text: crawlers see the
 * marketing copy, not a loading state.
 */
export function LandingAuthSlotPlaceholder() {
  return <div aria-busy="true" className="w-full" style={{ minHeight: "22rem" }} />;
}

/**
 * The auth-dependent part of the landing page: the returning-user
 * redirect, sign-in form, onboarding carousel, paywall, ?billing=success
 * handling, and `landing_viewed` analytics. Moved verbatim out of
 * app/page.tsx (which is now a server component rendering the static
 * marketing content around this island, so crawlers that don't run JS
 * still see it).
 *
 * The one behavioral difference is mechanical: where the old page returned
 * a full-page <LoadingScreen /> while `loading || checkingSavedLeagues`,
 * this island instead flags the landing root as pending (see
 * lib/landingPending.ts), which swaps the visible content for the same
 * server-rendered LoadingScreen via CSS. A returning user about to be
 * redirected still sees only the loading screen, never the marketing copy.
 */
export function LandingAuthIsland() {
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

  // Keeps the landing root's pending flag (LoadingScreen instead of the
  // marketing content) in sync with the real auth state, before paint.
  // While `loading`, leaves whatever the server HTML's inline script
  // decided alone: it already flagged a likely returning user, and
  // flipping a brand-new visitor's already-visible hero to a loader and
  // back would be a worse flash than either. Once auth resolves, the same
  // one-tick race the `landing_viewed` effect below documents applies
  // here: a session with a saved-leagues check that hasn't `"resolved"`
  // yet is still about to redirect (or about to start checking), so it
  // stays pending -- only a genuinely resolved, nothing-to-redirect-to
  // check (or no session at all) reveals the page.
  useLayoutEffect(() => {
    if (loading) return;
    setLandingPending(checkingSavedLeagues || (!!session && savedLeaguesCheck.current !== "resolved"));
  }, [loading, session, checkingSavedLeagues]);

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
    return <LandingAuthSlotPlaceholder />;
  }

  return accountReady ? (
    !carouselDone ? (
      <OnboardingCarousel onDone={() => setCarouselDone(true)} />
    ) : paywallDismissed ? (
      <SleeperImportForm onLeagueChosen={handleLeagueChosen} />
    ) : (
      <OnboardingPaywall onSkip={() => setPaywallDismissed(true)} />
    )
  ) : (
    <SignInForm onSignedIn={() => setAccountReady(true)} />
  );
}
