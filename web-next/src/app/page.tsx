import { Suspense } from "react";

import { AppStoreModules } from "@/components/AppStoreModules";
import { InlineScript } from "@/components/InlineScript";
import { LandingAuthIsland, LandingAuthSlotPlaceholder } from "@/components/LandingAuthIsland";
import { LandingShowcase } from "@/components/LandingShowcase";
import { LandingTrialHeadline } from "@/components/LandingTrialHeadline";
import { LoadingScreen } from "@/components/LoadingScreen";
import { SampleLeagueButton } from "@/components/SampleLeagueBanner";
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
const BENEFITS = ["Know your move this week", "Trades your league will accept", "Waivers ranked for your roster"];

export default function LandingPage() {
  return (
    <div id={LANDING_ROOT_ID} className="flex-1 flex flex-col" suppressHydrationWarning>
      <InlineScript html={LANDING_PENDING_SCRIPT} />
      <main className="fd-landing-content fd-landing-dark flex-1 flex flex-col items-center px-4 py-4 md:py-8">
        <div className="onboarding-field" aria-hidden="true" />
        <div className="onboarding-sweep" aria-hidden="true" />
        <div className="landing-grid">
          {/* Hero copy. The H1 is the coridian_-approved product line (do not
              rephrase without product). The sub line names features by their
              current names (Game Plan, not the retired "Next Move"). */}
          <div className="landing-hero flex flex-col gap-2">
            <h1 style={{ font: "var(--font-page-title)" }}>Your fantasy front office, not just a stats app.</h1>
            <p className="text-sm md:text-base" style={{ color: "var(--color-text-secondary)" }}>
              Real recommendations across your Game Plan, Trade Hub and Waivers, not raw data you have to interpret
              yourself.
            </p>
            <SampleLeagueButton surface="landing_hero" fullWidth={false} />
          </div>

          {/* Real screenshots (sample league data) lead the page. */}
          <LandingShowcase />

          <div className="landing-form flex flex-col gap-2">
            <LandingTrialHeadline />
            {/* useSearchParams() (for ?billing=success) needs a Suspense
                boundary or this page's static prerender fails the build.
                Only the island sits inside it. */}
            <Suspense fallback={<LandingAuthSlotPlaceholder />}>
              <LandingAuthIsland />
            </Suspense>
          </div>

          <div className="landing-extra flex flex-col gap-4">
            <ul className="flex flex-col gap-1.5 text-sm font-bold">
              {BENEFITS.map((line) => (
                <li key={line} className="flex items-center gap-2">
                  <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
                    ✓
                  </span>
                  {line}
                </li>
              ))}
            </ul>
            {/* Keep in step with ESPN_SUPPORTED_SEGMENTS in lib/leaguePlatform.ts
                and docs/platform-import-status.md: imported leagues get Dashboard,
                Matchup, My Team, Trade Analyzer, Players and League Rankings. */}
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Works with Sleeper leagues, plus public ESPN, Fleaflicker and MFL leagues (Dashboard, Matchup, My Team,
              Trade Analyzer, Players and League Rankings).
            </p>
            {/* Store slots stay quiet: Google Play is live, App Store is
                "Coming soon" until lib/appStoreLinks.ts has a URL. */}
            <AppStoreModules />
          </div>
        </div>
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
