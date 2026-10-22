import { Suspense } from "react";

import { AppStoreModules } from "@/components/AppStoreModules";
import { InlineScript } from "@/components/InlineScript";
import { LandingAuthIsland, LandingAuthSlotPlaceholder } from "@/components/LandingAuthIsland";
import { LoadingScreen } from "@/components/LoadingScreen";
import { LANDING_PENDING_SCRIPT, LANDING_ROOT_ID } from "@/lib/landingPending";

/**
 * Logged-out landing page. A server component: the hero, the Sleeper note,
 * and the app store module render into the static HTML, so crawlers and
 * link previewers that don't run JS (GPTBot, ClaudeBot, PerplexityBot, ...)
 * see what the product is instead of a bare "Loading…" splash. Same
 * pattern as legal/[pageKey] and methodology.
 *
 * Everything auth-dependent (returning-user redirect, sign-in form,
 * onboarding carousel, paywall, ?billing=success, `landing_viewed`
 * analytics) lives in the LandingAuthIsland client component, unchanged.
 *
 * Returning signed-in users still see only the branded LoadingScreen
 * before their auto-redirect, never a flash of this marketing content:
 * LANDING_PENDING_SCRIPT runs inline during HTML parsing (before first
 * paint) and flags the root as pending when a persisted Supabase session
 * is present, which CSS turns into "show the LoadingScreen, hide the
 * marketing view" (see .fd-landing-loader in globals.css). The island
 * then keeps that flag in sync with the real auth result. See
 * lib/landingPending.ts.
 */
export default function LandingPage() {
  return (
    <div id={LANDING_ROOT_ID} className="flex-1 flex flex-col" suppressHydrationWarning>
      <InlineScript html={LANDING_PENDING_SCRIPT} />
      <main className="fd-landing-content fd-landing-dark flex-1 flex flex-col items-center px-4 py-12 gap-10">
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
              audit, 2026-10-18), but nothing said so before reaching it.
              ESPN import (modules/espn_leagues.py) now covers exactly the
              pages named here; keep this line in step with
              ESPN_SUPPORTED_SEGMENTS in lib/leaguePlatform.ts. */}
          <p className="text-xs text-center" style={{ color: "var(--color-text-muted)" }}>
            Works with your Sleeper league. Public ESPN leagues work for My Team, Trade Analyzer, Players and League
            Rankings, with more on the way.
          </p>

          {/* useSearchParams() (for ?billing=success, see the island's
              paywallDismissed) requires a Suspense boundary around anything
              that calls it, or this page's otherwise-static prerender fails
              the build entirely — Next.js App Router's own documented
              requirement, not specific to this page. Only the island sits
              inside it, so the marketing content above and below still
              prerenders into the static HTML. */}
          <Suspense fallback={<LandingAuthSlotPlaceholder />}>
            <LandingAuthIsland />
          </Suspense>
        </div>

        {/* Native app store slots, below the primary sign-in action so they
            never compete with it. Each slot is "Coming soon" until its URL
            is set in lib/appStoreLinks.ts (the one-line go-live switch). */}
        <AppStoreModules />
      </main>
      {/* Hidden unless the root is flagged pending (returning user about to
          be redirected). After the marketing content in DOM order so a
          no-JS reader meets the real copy first. */}
      <div className="fd-landing-loader flex-1 flex-col">
        <LoadingScreen />
      </div>
    </div>
  );
}
