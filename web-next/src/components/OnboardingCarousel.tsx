"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/Button";
import { useExperienceLevel } from "@/context/ExperienceLevelContext";
import { BRAND_NAME } from "@/lib/brand";
import { PLAIN_COPY, type ExperienceLevel } from "@/lib/experienceCopy";
import { experienceBucket, trackOnboarding, trackOnboardingStepViewed } from "@/lib/onboardingAnalytics";

/**
 * Signup onboarding carousel — Zach, 2026-10-18: "we need a more
 * onboarding. We need at least 3 pgs on sign up abt who we are and what we
 * solve and how it works and ask if the user is a beginner or advanced."
 * Reworked 2026-10-22 (owner: the sample-card slide was "too basic"): one
 * swipeable slide per feature, each led by a real screenshot of that page
 * in a phone frame with a one-line benefit below, then Connect, then the
 * experience picker. Shown once, right after a brand-new account's first
 * sign-in, before OnboardingPaywall.
 *
 * The screenshots (public/onboarding/*.webp, mirrored in mobile/assets/
 * onboarding/) are captured from this app's real UI against a generic
 * sample league: no real users' data. Keep FEATURES in lockstep with
 * mobile's OnboardingScreen.tsx.
 *
 * Deliberately a fixed dark/cinematic treatment regardless of the app's
 * normal light/dark theme toggle — this is a one-time, brief intro screen,
 * not a persistent themed surface.
 */
export const ONBOARDING_FEATURES = [
  { key: "gameplan", title: "Game Plan", benefit: "One clear top priority every time you open the app." },
  { key: "tradehub", title: "Trade Hub", benefit: "Trade ideas your league partners would actually accept." },
  { key: "matchup", title: "Matchup", benefit: "Win odds for your week, before kickoff." },
  { key: "planner", title: "Lineup Planner", benefit: "See what a swap does to your win odds." },
  { key: "pqv", title: "Player Quick View", benefit: "Value, usage, and fit for any player in one tap." },
  { key: "playoff", title: "Playoff Odds", benefit: "Simulated playoff odds for every team in your league." },
  { key: "tendencies", title: "Manager Tendencies", benefit: "Know how each manager trades before you pitch." },
  { key: "waivers", title: "Waivers", benefit: "Priority Adds ranked for your roster, with FAAB ranges." },
] as const;

const SWIPE_THRESHOLD_PX = 50;

export function OnboardingCarousel({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [level, setLevel] = useState<ExperienceLevel | null>(null);
  const [saving, setSaving] = useState(false);
  const touchStartX = useRef<number | null>(null);
  const { setLevel: saveExperienceLevel } = useExperienceLevel();

  const featureCount = ONBOARDING_FEATURES.length;
  const connectStep = featureCount;
  const levelStep = featureCount + 1;
  const totalSteps = featureCount + 2;

  const stepName = (i: number) => (i < featureCount ? ONBOARDING_FEATURES[i].key : i === connectStep ? "connect" : "level");

  // One step_viewed per step per session (deduped in the helper), so a
  // re-render or a Back/Next revisit never double counts.
  useEffect(() => {
    trackOnboardingStepViewed(stepName(step), step);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  const finish = async () => {
    if (!level) return;
    trackOnboarding("completed", { step: "level", step_index: levelStep, experience: experienceBucket(level) });
    setSaving(true);
    try {
      // Saved through ExperienceLevelContext so the answer takes effect
      // right away (lib/experienceCopy.ts beginner helper text), not only
      // after the next page load.
      await saveExperienceLevel(level);
    } catch {
      // Best-effort — a failed preference write should never block
      // onboarding itself; the answer can be changed later on the Account
      // page's Explanations setting.
    }
    setSaving(false);
    onDone();
  };

  const next = () => {
    if (step === levelStep) {
      void finish();
      return;
    }
    setStep((s) => s + 1);
  };
  const back = () => {
    if (step > 0) trackOnboarding("back", { step: stepName(step), step_index: step });
    setStep((s) => Math.max(0, s - 1));
  };
  const skip = () => {
    trackOnboarding("skipped", { step: stepName(step), step_index: step });
    onDone();
  };
  const pickLevel = (value: ExperienceLevel) => {
    setLevel(value);
    trackOnboarding("experience_selected", { experience: experienceBucket(value) });
  };

  const onTouchEnd = (clientX: number) => {
    const start = touchStartX.current;
    touchStartX.current = null;
    if (start === null) return;
    const dx = clientX - start;
    // The last step ends in an explicit choice, so a swipe never skips it.
    if (dx <= -SWIPE_THRESHOLD_PX && step < levelStep) setStep(step + 1);
    else if (dx >= SWIPE_THRESHOLD_PX) back();
  };

  const feature = step < featureCount ? ONBOARDING_FEATURES[step] : null;

  return (
    <div className="onboarding-shell">
      <div className="onboarding-field" aria-hidden="true" />
      <div className="onboarding-sweep" aria-hidden="true" />

      <div
        className="onboarding-content"
        onTouchStart={(e) => {
          touchStartX.current = e.touches[0]?.clientX ?? null;
        }}
        onTouchEnd={(e) => onTouchEnd(e.changedTouches[0]?.clientX ?? 0)}
      >
        <div className="onboarding-topbar">
          <div className="onboarding-dots">
            {Array.from({ length: totalSteps }).map((_, i) => (
              <span key={i} className={`onboarding-dot${i === step ? " onboarding-dot--active" : ""}`} />
            ))}
          </div>
          <button type="button" onClick={skip} className="onboarding-skip">
            Skip
          </button>
        </div>

        {feature ? (
          <div className="onboarding-section onboarding-section--center onboarding-feature">
            <span className="onboarding-eyebrow">{feature.title}</span>
            <div className="onboarding-phone">
              <Image
                src={`/onboarding/onboarding-${feature.key}.webp`}
                alt={`${feature.title} screen, shown with sample league data`}
                width={600}
                height={1298}
                priority={step === 0}
                className="onboarding-phone-img"
              />
            </div>
            <p className="onboarding-benefit">{feature.benefit}</p>
          </div>
        ) : null}

        {step === connectStep ? (
          <div className="onboarding-hero">
            <Image src="/brand-mark-white.png" alt="" width={56} height={56} className="onboarding-mark" />
            <span className="onboarding-eyebrow">One setup step</span>
            <h1 className="onboarding-headline onboarding-headline--sm">Connect Sleeper or ESPN</h1>
            <p className="onboarding-body">Every recommendation is built around your league.</p>
          </div>
        ) : null}

        {step === levelStep ? (
          <div className="onboarding-section onboarding-section--center">
            <span className="onboarding-eyebrow">Last thing</span>
            <h1 className="onboarding-headline onboarding-headline--sm">How much dynasty experience do you have?</h1>
            <p className="onboarding-body onboarding-body--center">
              Tunes how much explanation shows up alongside recommendations. Change it anytime in Settings.
            </p>
            <p className="onboarding-body onboarding-body--center">{PLAIN_COPY.onboardingDynastyNote}</p>
            <div className="onboarding-cards" style={{ marginTop: "var(--space-md)" }}>
              <button
                type="button"
                onClick={() => pickLevel("beginner")}
                className={`onboarding-glass onboarding-pick${level === "beginner" ? " onboarding-pick--selected" : ""}`}
              >
                <div className="onboarding-row">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="2" aria-hidden="true">
                    <path d="M12 21V11M12 11C12 7 9 5 5 5c0 4 2.5 6.5 7 6M12 11c0-3.5 2-5.5 6-5.5 0 3.5-2 5.5-6 5.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="onboarding-row-title">New to dynasty</span>
                </div>
                <span className="onboarding-row-body">
                  Explain the why behind every recommendation — trade logic, value, roster strategy.
                </span>
              </button>
              <button
                type="button"
                onClick={() => pickLevel("advanced")}
                className={`onboarding-glass onboarding-pick${level === "advanced" ? " onboarding-pick--selected" : ""}`}
              >
                <div className="onboarding-row">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-premium)" strokeWidth="2" aria-hidden="true">
                    <path d="M8 21h8M12 17v4M6 4h12v3a6 6 0 0 1-12 0V4z" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M6 5H4a2 2 0 0 0 0 4h2M18 5h2a2 2 0 0 1 0 4h-2" strokeLinecap="round" />
                  </svg>
                  <span className="onboarding-row-title">I know my stuff</span>
                </div>
                <span className="onboarding-row-body">Skip the explanations — just the call, the value, and the confidence.</span>
              </button>
            </div>
          </div>
        ) : null}

        <div className="onboarding-footer">
          {step > 0 ? (
            <button type="button" onClick={back} className="onboarding-back">
              Back
            </button>
          ) : null}
          <Button
            onClick={next}
            disabled={(step === levelStep && !level) || saving}
            className="flex-1"
            style={{ alignSelf: "auto" }}
          >
            {step === levelStep
              ? saving
                ? `Setting up ${BRAND_NAME}…`
                : "Continue"
              : "Next"}
          </Button>
        </div>
      </div>
    </div>
  );
}
