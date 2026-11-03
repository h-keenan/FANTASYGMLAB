import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";

import { AppStoreModules } from "@/components/AppStoreModules";
import { InlineScript } from "@/components/InlineScript";
import { LandingAuthIsland, LandingAuthSlotPlaceholder } from "@/components/LandingAuthIsland";
import { LandingScreens } from "@/components/LandingScreens";
import { LandingTrialHeadline } from "@/components/LandingTrialHeadline";
import { LoadingScreen } from "@/components/LoadingScreen";
import { SampleLeagueButton } from "@/components/SampleLeagueBanner";
import { ValuesCredit } from "@/components/ValuesCredit";
import { LANDING_SHARE_SCRIPT } from "@/lib/landingShare";
import { absoluteUrl, OG_IMAGE } from "@/lib/seo/site";
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
const TITLE = "FantasyDesk: roster-aware dynasty trades, waivers and rankings";
const DESCRIPTION =
  "Roster-aware dynasty trades, waivers and a weekly Game Plan built from your real league. Try a full sample league with no account or card.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: absoluteUrl("/") },
  // A page-level openGraph replaces the layout's wholesale, so repeat images.
  openGraph: { title: TITLE, description: DESCRIPTION, url: absoluteUrl("/"), type: "website", siteName: "FantasyDesk", images: [OG_IMAGE] },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: [OG_IMAGE.url] },
};

const SHARE_HEADLINE = "Someone shared a FantasyDesk trade verdict. Get yours for your own league.";

const STEPS = [
  { title: "Connect your league", body: "Use your Sleeper username, or a public ESPN, Fleaflicker or MFL league." },
  { title: "We read your roster", body: "Real player values, matched to your lineup, depth and what each manager needs." },
  { title: "Get your next move", body: "A clear verdict on trades, waivers and your lineup, with the reasons why." },
] as const;

const FEATURES = [
  { title: "Trade verdicts that know your roster", body: "See if a trade helps your team before you send it, based on your needs and what your partner would accept." },
  { title: "Waivers that fit your team", body: "Pickups ranked for your roster, with FAAB ranges, so you stop chasing names that do not help you." },
  { title: "Start/sit with weather and matchup", body: "Lineup calls that account for the opponent and game-day weather, with win odds for your week." },
  { title: "League intelligence", body: "See how each manager trades, who is contending, and simulated playoff odds for every team." },
] as const;

const FOOTER_LINKS = [
  { href: "/dynasty-tools", label: "Dynasty tools" },
  { href: "/dynasty-rankings/qb", label: "Dynasty rankings" },
  { href: "/trade-analyzer", label: "Free trade analyzer" },
  { href: "/dynasty-trade-value-chart", label: "Trade value chart" },
  { href: "/methodology", label: "How we evaluate" },
  { href: "/legal/terms", label: "Terms" },
  { href: "/legal/privacy", label: "Privacy" },
  { href: "/legal/no_affiliation", label: "No-affiliation disclaimer" },
] as const;

export default function LandingPage() {
  return (
    <div id={LANDING_ROOT_ID} className="flex-1 flex flex-col" suppressHydrationWarning>
      <InlineScript html={LANDING_PENDING_SCRIPT} />
      <InlineScript html={LANDING_SHARE_SCRIPT} />
      <main className="fd-landing-content fd-landing-dark flex-1 flex flex-col items-center px-4 py-4 md:py-8">
        <div className="onboarding-field" aria-hidden="true" />
        <div className="onboarding-sweep" aria-hidden="true" />
        <div className="lp">
          {/* Hero. Built for someone who scanned a share-card QR and has
              seconds to decide: logo, one promise, one primary action
              (sample league: value before any account wall; guests cannot
              buy, so nothing here starts a purchase), one secondary (own
              league, which means the account form below), and the store
              links. For utm_campaign=share_card the h1 swaps to the shared-
              analysis line via a pre-paint flag (lib/landingShare.ts); no
              data is carried in the URL. */}
          <header className="lp-hero lp-marketing">
            <Image
              src="/share-card/lockup-white.png"
              alt="FantasyDesk"
              width={1102}
              height={160}
              priority
              className="lp-logo"
            />
            <h1 className="lp-h1">
              <span className="lp-default-only">Get the trade your leaguemate would actually accept.</span>
              <span className="lp-share-only">{SHARE_HEADLINE}</span>
            </h1>
            <p className="lp-sub">
              Roster-aware dynasty trades, waivers and a weekly Game Plan, built from your real league like a front
              office would.
            </p>
            <div className="lp-cta">
              <SampleLeagueButton surface="landing_hero" variant="primary" />
              <a href="#get-started" className="lp-cta-secondary">
                Import your league
              </a>
            </div>
            <p className="lp-note">Look around a full sample league free: no account or card needed.</p>
            {/* Google Play is live; the App Store slot stays "Coming soon"
                until lib/appStoreLinks.ts has a URL. */}
            <AppStoreModules />
          </header>

          <section aria-labelledby="lp-how-heading" className="lp-section lp-marketing">
            <h2 id="lp-how-heading" className="lp-h2">
              How it works
            </h2>
            <ol className="lp-steps">
              {STEPS.map((step, i) => (
                <li key={step.title} className="lp-step">
                  <span className="lp-step-num" aria-hidden="true">
                    {i + 1}
                  </span>
                  <div>
                    <h3 className="lp-h3">{step.title}</h3>
                    <p className="lp-body">{step.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section aria-labelledby="lp-features-heading" className="lp-section lp-marketing">
            <h2 id="lp-features-heading" className="lp-h2">
              Built for the decisions you actually make
            </h2>
            <ul className="lp-features">
              {FEATURES.map((f) => (
                <li key={f.title} className="lp-feature onboarding-glass">
                  <h3 className="lp-h3">{f.title}</h3>
                  <p className="lp-body">{f.body}</p>
                </li>
              ))}
            </ul>
          </section>

          <LandingScreens />

          <section id="get-started" aria-labelledby="lp-start-heading" className="lp-section lp-start">
            <h2 id="lp-start-heading" className="lp-h2 lp-marketing">
              Create your account
            </h2>
            <div className="lp-marketing">
              <LandingTrialHeadline />
            </div>
            {/* useSearchParams() (for ?billing=success) needs a Suspense
                boundary or this page's static prerender fails the build.
                Only the island sits inside it. */}
            <Suspense fallback={<LandingAuthSlotPlaceholder />}>
              <LandingAuthIsland />
            </Suspense>
            {/* Keep in step with ESPN_SUPPORTED_SEGMENTS in lib/leaguePlatform.ts
                and docs/platform-import-status.md: imported leagues get Dashboard,
                Matchup, My Team, Trade Analyzer, Players and League Rankings. */}
            <p className="lp-note lp-marketing">
              Works with Sleeper leagues, plus public ESPN, Fleaflicker and MFL leagues (Dashboard, Matchup, My Team,
              Trade Analyzer, Players and League Rankings).
            </p>
          </section>

          <footer className="lp-footer">
            <nav aria-label="Footer">
              <ul className="lp-footer-links">
                {FOOTER_LINKS.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href}>{l.label}</Link>
                  </li>
                ))}
              </ul>
            </nav>
            <ValuesCredit />
          </footer>
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
