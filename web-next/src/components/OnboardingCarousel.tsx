"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { usePortalRoot } from "@/components/OnboardingShell";

import { Button } from "@/components/Button";
import { PillRow } from "@/components/PillRow";
import { useExperienceLevel } from "@/context/ExperienceLevelContext";
import { ONBOARDING_FEATURES, ONBOARDING_STEP_KEYS } from "@/lib/onboardingFeatures";
import { OnboardingValueSlides } from "@/components/OnboardingValueSlides";
import {
  EXPERIENCE_GOAL_OPTIONS,
  EXPERIENCE_LEVEL_OPTIONS,
  PLAIN_COPY,
  type ExperienceGoal,
  type ExperienceLevel,
} from "@/lib/experienceCopy";
import { trackFeatureUse } from "@/lib/analytics";
import { experienceBucket, trackOnboarding, trackOnboardingStepViewed } from "@/lib/onboardingAnalytics";

const LEVEL_ICONS: Record<ExperienceLevel, { stroke: string; path: string }> = {
  new_to_fantasy: {
    stroke: "var(--color-accent)",
    path: "M12 2l2.2 6.6H21l-5.4 4 2.1 6.6L12 15.2 6.3 19.2l2.1-6.6L3 8.6h6.8z",
  },
  beginner: {
    stroke: "var(--color-success)",
    path: "M12 21V11M12 11C12 7 9 5 5 5c0 4 2.5 6.5 7 6M12 11c0-3.5 2-5.5 6-5.5 0 3.5-2 5.5-6 5.5",
  },
  advanced: {
    stroke: "var(--color-premium)",
    path: "M8 21h8M12 17v4M6 4h12v3a6 6 0 0 1-12 0V4z M6 5H4a2 2 0 0 0 0 4h2M18 5h2a2 2 0 0 1 0 4h-2",
  },
};
const GOAL_OPTIONS = (Object.keys(EXPERIENCE_GOAL_OPTIONS) as ExperienceGoal[]).map((value) => ({
  value,
  label: EXPERIENCE_GOAL_OPTIONS[value].label,
}));

/**
 * Signup onboarding carousel — Zach, 2026-10-18: "we need a more
 * onboarding. We need at least 3 pgs on sign up abt who we are and what we
 * solve and how it works and ask if the user is a beginner or advanced."
 * Cut from 10 steps to 3 on 2026-10-23 (coridian_: "10 is insane"), then to
 * 2 on 2026-11-10: (1) the experience picker FIRST (one tap, before any
 * jargon; Skip means "decide later", never "veteran"), (2) a value line over
 * auto-advancing real screenshots. The old Connect info slide is gone: the
 * real connect form is the very next screen. The full 8-screen feature tour
 * lives on in replay mode (Account > Replay the tour). Shown once, right
 * after a brand-new account's first sign-in; the trial offer comes AFTER the
 * league connects (LandingAuthIsland).
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
export { ONBOARDING_FEATURES };

const SWIPE_THRESHOLD_PX = 50;

export function OnboardingCarousel({ onDone, replay = false }: { onDone: () => void; replay?: boolean }) {
  const [step, setStep] = useState(0);
  const [level, setLevel] = useState<ExperienceLevel | null>(null);
  // Optional, skippable — never gates Continue, unlike level.
  const [goal, setGoal] = useState<ExperienceGoal | null>(null);
  const [saving, setSaving] = useState(false);
  const touchStartX = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);
  // The shell is portaled to <body>. Rendered in place it sat inside the
  // landing page's z-index:1 stacking context, so the site Header and the
  // backdrop-filter store badges painted over it on iOS Safari. While it is
  // open every other <body> child is made inert + aria-hidden.
  const portalRoot = usePortalRoot();
  const [direction, setDirection] = useState<"next" | "back">("next");
  const { setLevel: saveExperienceLevel, setGoal: saveExperienceGoal } = useExperienceLevel();

  const featureCount = ONBOARDING_FEATURES.length;
  // Replay (Account > "Replay the tour"): all feature slides, nothing else.
  // No connect or experience step, so nothing is saved, no step_viewed/
  // completed events (the signup funnel stays clean) and onboarding-completed
  // is untouched. Signup is 2 steps: level, value.
  const levelStep = replay ? -1 : 0;
  const valueStep = replay ? -1 : 1;
  const lastStep = replay ? featureCount - 1 : valueStep;
  const totalSteps = replay ? featureCount : ONBOARDING_STEP_KEYS.length;

  const stepName = (i: number): string => (replay ? ONBOARDING_FEATURES[i].key : ONBOARDING_STEP_KEYS[i]);

  // One step_viewed per step per session (deduped in the helper), so a
  // re-render or a Back/Next revisit never double counts.
  useEffect(() => {
    if (replay) return;
    trackOnboardingStepViewed(stepName(step), step);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  // Saves the level (and optional goal) as soon as the first step is
  // answered, so beginner help is live for the rest of onboarding.
  const saveAnswers = async () => {
    if (!level) return;
    trackOnboarding("completed", { step: "level", step_index: levelStep, experience: experienceBucket(level) });
    setSaving(true);
    try {
      // Saved through ExperienceLevelContext so the answer takes effect
      // right away (lib/experienceCopy.ts beginner helper text), not only
      // after the next page load.
      await saveExperienceLevel(level);
    } catch {
      // Best-effort: a failed preference write never blocks onboarding; the
      // answer can be changed later on Account > Explanations.
    }
    if (goal) {
      try {
        await saveExperienceGoal(goal);
      } catch {
        // Best-effort.
      }
    }
    setSaving(false);
    setDirection("next");
    setStep(valueStep);
  };

  const finish = () => {
    if (!replay) trackFeatureUse("onboarding_completed", { props: { experience: level ? experienceBucket(level) : undefined } });
    onDone();
  };

  const next = () => {
    if (replay && step === lastStep) {
      onDone();
      return;
    }
    if (step === levelStep) {
      void saveAnswers();
      return;
    }
    if (step === valueStep) {
      finish();
      return;
    }
    setDirection("next");
    setStep((s) => s + 1);
  };
  const back = () => {
    if (step > 0 && !replay) trackOnboarding("back", { step: stepName(step), step_index: step });
    setDirection("back");
    setStep((s) => Math.max(0, s - 1));
  };
  const skip = () => {
    if (replay) {
      onDone();
      return;
    }
    trackOnboarding("skipped", { step: stepName(step), step_index: step });
    // First-run paywall-after-connect (2026-11): "Decide later" / "Skip" leaves
    // the intro in ONE tap (level stays unanswered: beginner-lite help). The
    // next screen is the connect step, never a paywall.
    onDone();
  };
  const pickLevel = (value: ExperienceLevel) => {
    setLevel(value);
    trackOnboarding("experience_selected", { experience: experienceBucket(value) });
  };
  // Tapping the already-selected chip clears it (it's optional — unlike level).
  const pickGoal = (value: string) => {
    setGoal((current) => (current === value ? null : (value as ExperienceGoal)));
  };

  const onTouchEnd = (clientX: number, clientY: number) => {
    const start = touchStartX.current;
    const startY = touchStartY.current;
    touchStartX.current = null;
    touchStartY.current = null;
    if (start === null) return;
    const dx = clientX - start;
    // Mostly-vertical gestures are scrolls, never slide changes.
    if (startY !== null && Math.abs(clientY - startY) > Math.abs(dx)) return;
    // The first step is an explicit choice, so a swipe never skips it.
    if (dx <= -SWIPE_THRESHOLD_PX && step < lastStep && step !== levelStep) {
      setDirection("next");
      setStep(step + 1);
    }
    else if (dx >= SWIPE_THRESHOLD_PX) back();
  };

  const feature = replay ? ONBOARDING_FEATURES[step] : null;
  const showValue = !replay && step === valueStep;

  const nextFeature = replay && step + 1 < featureCount ? ONBOARDING_FEATURES[step + 1] : null;

  if (!portalRoot) return null;
  return createPortal(
    <div className="onboarding-shell" role="region" aria-label="Welcome tour">
      <div className="onboarding-aurora" aria-hidden="true" />
      <div className="onboarding-field" aria-hidden="true" />
      <div className="onboarding-sweep" aria-hidden="true" />

      <div
        className="onboarding-content"
        onTouchStart={(e) => {
          touchStartX.current = e.touches[0]?.clientX ?? null;
          touchStartY.current = e.touches[0]?.clientY ?? null;
        }}
        onTouchEnd={(e) => onTouchEnd(e.changedTouches[0]?.clientX ?? 0, e.changedTouches[0]?.clientY ?? 0)}
      >
        <div className="onboarding-topbar">
          <div className="onboarding-dots" role="img" aria-label={`Step ${step + 1} of ${totalSteps}`}>
            {Array.from({ length: totalSteps }).map((_, i) => (
              <span key={i} aria-hidden="true" className={`onboarding-dot${i === step ? " onboarding-dot--active" : ""}`} />
            ))}
          </div>
          <button type="button" onClick={skip} className="onboarding-skip">
            {step === levelStep ? "Decide later" : "Skip"}
          </button>
        </div>

        <div className="onboarding-scroll">
        {feature ? (
          <div key={step} className={`onboarding-section onboarding-section--center onboarding-feature onboarding-slide onboarding-slide--${direction}`}>
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

        {showValue ? <OnboardingValueSlides direction={direction} /> : null}

        {step === levelStep ? (
          <div className="onboarding-section onboarding-section--center">
            <span className="onboarding-eyebrow">One quick question</span>
            <h1 className="onboarding-headline onboarding-headline--sm">
              How familiar are you with <span className="onboarding-gradient">fantasy football</span>?
            </h1>
            <p className="onboarding-body onboarding-body--center">
              Tunes how much explanation shows up alongside recommendations. Change it anytime in Settings.
            </p>
            <p className="onboarding-body onboarding-body--center">{PLAIN_COPY.onboardingDynastyNote}</p>
            <div className="onboarding-cards" style={{ marginTop: "var(--space-md)" }}>
              {(Object.keys(EXPERIENCE_LEVEL_OPTIONS) as ExperienceLevel[]).map((value) => {
                const option = EXPERIENCE_LEVEL_OPTIONS[value];
                const icon = LEVEL_ICONS[value];
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => pickLevel(value)}
                    className={`onboarding-glass onboarding-pick${level === value ? " onboarding-pick--selected" : ""}`}
                  >
                    <div className="onboarding-row">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={icon.stroke} strokeWidth="2" aria-hidden="true">
                        <path d={icon.path} strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <span className="onboarding-row-title">{option.title}</span>
                    </div>
                    <span className="onboarding-row-body">{option.body}</span>
                  </button>
                );
              })}
            </div>
            <div className="flex flex-col gap-2 w-full" style={{ marginTop: "var(--space-lg)" }}>
              <span className="onboarding-body onboarding-body--center">{PLAIN_COPY.experienceGoalPrompt}</span>
              <PillRow
                ariaLabel={PLAIN_COPY.experienceGoalPrompt}
                options={GOAL_OPTIONS}
                active={goal ?? ""}
                onSelect={pickGoal}
              />
              <span className="text-xs onboarding-body--center" style={{ color: "var(--color-text-muted)" }}>
                {PLAIN_COPY.experienceGoalOptionalNote}
              </span>
            </div>
          </div>
        ) : null}

        {nextFeature ? (
          // Warms the next slide's screenshot so swiping never shows a blank frame.
          <div aria-hidden="true" className="onboarding-preload">
            <Image
              src={`/onboarding/onboarding-${nextFeature.key}.webp`}
              alt=""
              width={600}
              height={1298}
              loading="eager"
            />
          </div>
        ) : null}
        </div>

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
            {replay ? (step === lastStep ? "Done" : "Next") : step === valueStep ? "Connect my league" : "Continue"}
          </Button>
        </div>
      </div>
    </div>,
    portalRoot,
  );
}
