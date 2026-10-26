"use client";

import Image from "next/image";
import { useEffect, useState, useSyncExternalStore } from "react";

import {
  ONBOARDING_FEATURES,
  ONBOARDING_VALUE_HEADLINE,
  ONBOARDING_VALUE_SLIDE_KEYS,
  ONBOARDING_VALUE_SLIDE_MS,
} from "@/lib/onboardingFeatures";

const SLIDES = ONBOARDING_VALUE_SLIDE_KEYS.map((key) => ONBOARDING_FEATURES.find((f) => f.key === key)!);

/**
 * Step 1 of onboarding: one value line over a phone frame that auto-advances
 * through a few real screenshots. The slides are inside one step (no extra
 * funnel steps). Auto-advance is off under prefers-reduced-motion and can be
 * paused; tapping a dot jumps and stops the timer.
 */
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(onChange: () => void) {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const mq = window.matchMedia(REDUCED_MOTION_QUERY);
  mq.addEventListener?.("change", onChange);
  return () => mq.removeEventListener?.("change", onChange);
}

function getReducedMotion() {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

/** Gradient on the last word of the headline (the "Signal" accent). */
function renderHeadline(text: string) {
  const idx = text.lastIndexOf(" ");
  if (idx < 0) return <span className="onboarding-gradient">{text}</span>;
  return (
    <>
      {text.slice(0, idx + 1)}
      <span className="onboarding-gradient">{text.slice(idx + 1)}</span>
    </>
  );
}

export function OnboardingValueSlides({ direction }: { direction: "next" | "back" }) {
  const [slide, setSlide] = useState(0);
  const [paused, setPaused] = useState(false);
  const reduced = useSyncExternalStore(subscribeReducedMotion, getReducedMotion, () => false);

  const auto = !paused && !reduced;
  useEffect(() => {
    if (!auto) return;
    const id = window.setInterval(() => setSlide((s) => (s + 1) % SLIDES.length), ONBOARDING_VALUE_SLIDE_MS);
    return () => window.clearInterval(id);
  }, [auto]);

  const current = SLIDES[slide];
  const upcoming = SLIDES[(slide + 1) % SLIDES.length];

  return (
    <div className={`onboarding-section onboarding-section--center onboarding-feature onboarding-feature--value onboarding-slide onboarding-slide--${direction}`}>
      <span className="onboarding-eyebrow">{current.title}</span>
      <h1 className="onboarding-headline onboarding-headline--sm">{renderHeadline(ONBOARDING_VALUE_HEADLINE)}</h1>
      <div className="onboarding-phone">
        <Image
          key={current.key}
          src={`/onboarding/onboarding-${current.key}.webp`}
          alt={`${current.title} screen, shown with sample league data`}
          width={600}
          height={1298}
          priority={slide === 0}
          className="onboarding-phone-img onboarding-slide--next"
        />
      </div>
      <p className="onboarding-benefit">{current.benefit}</p>
      <div className="onboarding-value-controls">
        <div className="onboarding-value-dots" role="group" aria-label="Preview screens">
          {SLIDES.map((s, i) => (
            <button
              key={s.key}
              type="button"
              className={`onboarding-value-dot${i === slide ? " onboarding-value-dot--active" : ""}`}
              aria-label={`Show ${s.title}`}
              aria-current={i === slide ? "true" : undefined}
              onClick={() => {
                setSlide(i);
                setPaused(true);
              }}
            />
          ))}
        </div>
        {!reduced ? (
          <button type="button" className="onboarding-back" onClick={() => setPaused((p) => !p)}>
            {paused ? "Play previews" : "Pause previews"}
          </button>
        ) : null}
      </div>
      <div aria-hidden="true" className="onboarding-preload">
        <Image src={`/onboarding/onboarding-${upcoming.key}.webp`} alt="" width={600} height={1298} loading="eager" />
      </div>
    </div>
  );
}
