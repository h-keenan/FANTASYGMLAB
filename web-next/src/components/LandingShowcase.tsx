"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";

import { ONBOARDING_FEATURES } from "@/lib/onboardingFeatures";

/** The real screens worth leading with, in order. Same screenshots and
 *  benefit lines as the signup carousel (lib/onboardingFeatures.ts). */
const SHOWCASE_KEYS = ["gameplan", "tradehub", "matchup", "pqv", "playoff", "waivers"] as const;

/** Time each slide stays active before advancing. */
export const SHOWCASE_SLIDE_MS = 4500;
/** Autoplay resumes this long after the last interaction ends. */
export const SHOWCASE_RESUME_MS = 4000;

/**
 * Landing-page product strip: real screenshots (sample league data) in phone
 * frames, one benefit line under each. A CSS scroll-snap row, so it is
 * swipeable on touch and the first slide renders fully on the server. After
 * hydration it auto-advances every ~4.5s; the active screenshot slowly zooms
 * in (transform only) and eases back out as it scrolls away. Autoplay pauses on
 * hover/focus/touch/manual scroll, when off-screen, when the tab is hidden, via
 * a pause button (WCAG 2.2.2), and never runs under prefers-reduced-motion.
 */
export function LandingShowcase() {
  const items = SHOWCASE_KEYS.map((key) => ONBOARDING_FEATURES.find((f) => f.key === key)!);
  const count = items.length;

  const sectionRef = useRef<HTMLElement>(null);
  const trackRef = useRef<HTMLUListElement>(null);

  const [active, setActive] = useState(0);
  const [reduced, setReduced] = useState(true); // SSR/pre-hydration: no motion
  const [userPaused, setUserPaused] = useState(false);
  const [interacting, setInteracting] = useState(false);
  const [visible, setVisible] = useState(false);
  const [tabVisible, setTabVisible] = useState(true);

  const playing = !reduced && !userPaused && !interacting && visible && tabVisible;

  // Reduced-motion preference (live).
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(mq.matches);
    sync();
    mq.addEventListener?.("change", sync);
    return () => mq.removeEventListener?.("change", sync);
  }, []);

  // Pause when scrolled off-screen.
  useEffect(() => {
    const el = sectionRef.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver((entries) => {
      const last = entries[entries.length - 1];
      if (last) setVisible(last.isIntersecting);
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // Pause when the tab is hidden.
  useEffect(() => {
    const sync = () => setTabVisible(document.visibilityState !== "hidden");
    sync();
    document.addEventListener("visibilitychange", sync);
    return () => document.removeEventListener("visibilitychange", sync);
  }, []);

  const scrollToIndex = useCallback((index: number) => {
    const track = trackRef.current;
    const li = track?.children[index] as HTMLElement | undefined;
    if (!track || !li || typeof track.scrollTo !== "function") return;
    const pad = parseFloat(getComputedStyle(track).paddingLeft) || 0;
    const left = li.getBoundingClientRect().left - track.getBoundingClientRect().left + track.scrollLeft - pad;
    track.scrollTo({ left, behavior: "smooth" });
  }, []);

  // Auto-advance timer: one timeout per active slide while playing.
  useEffect(() => {
    if (!playing) return;
    const id = setTimeout(() => {
      const next = (active + 1) % count;
      setActive(next);
      scrollToIndex(next);
    }, SHOWCASE_SLIDE_MS);
    return () => clearTimeout(id);
  }, [playing, active, count, scrollToIndex]);

  // Interaction pause: stays paused until RESUME_MS after the last one ends.
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearResume = useCallback(() => {
    if (resumeTimer.current) clearTimeout(resumeTimer.current);
    resumeTimer.current = null;
  }, []);
  const beginHold = useCallback(() => {
    clearResume();
    setInteracting(true);
  }, [clearResume]);
  const endHold = useCallback(() => {
    clearResume();
    resumeTimer.current = setTimeout(() => {
      resumeTimer.current = null;
      setInteracting(false);
    }, SHOWCASE_RESUME_MS);
  }, [clearResume]);
  useEffect(() => clearResume, [clearResume]);

  // Track which slide a manual swipe settled on (ignored while autoplaying,
  // since the timer owns `active` then).
  const settleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onScroll = () => {
    if (playing) return;
    if (settleTimer.current) clearTimeout(settleTimer.current);
    settleTimer.current = setTimeout(() => {
      const track = trackRef.current;
      if (!track) return;
      const base = track.getBoundingClientRect().left;
      const pad = parseFloat(getComputedStyle(track).paddingLeft) || 0;
      let best = 0;
      let bestDist = Infinity;
      Array.from(track.children).forEach((child, i) => {
        const dist = Math.abs(child.getBoundingClientRect().left - base - pad);
        if (dist < bestDist) {
          bestDist = dist;
          best = i;
        }
      });
      if (track.scrollLeft + track.clientWidth >= track.scrollWidth - 2) best = count - 1;
      setActive(best);
    }, 120);
  };
  useEffect(
    () => () => {
      if (settleTimer.current) clearTimeout(settleTimer.current);
    },
    [],
  );

  const holdProps = {
    onPointerEnter: (e: React.PointerEvent) => {
      if (e.pointerType === "mouse") beginHold();
    },
    onPointerLeave: (e: React.PointerEvent) => {
      if (e.pointerType === "mouse") endHold();
    },
    onPointerDown: beginHold,
    onPointerUp: endHold,
    onPointerCancel: endHold,
    onTouchStart: beginHold,
    onTouchEnd: endHold,
    onTouchCancel: endHold,
    onWheel: () => {
      beginHold();
      endHold();
    },
    onFocus: beginHold,
    onBlur: endHold,
  };

  const goTo = (i: number) => {
    beginHold();
    setActive(i);
    scrollToIndex(i);
    endHold();
  };

  return (
    <section
      ref={sectionRef}
      aria-label="What FantasyDesk looks like"
      aria-roledescription="carousel"
      className="landing-showcase"
      data-playing={playing ? "true" : "false"}
      {...holdProps}
    >
      <ul ref={trackRef} className="landing-showcase-track" aria-live={playing ? "off" : "polite"} onScroll={onScroll}>
        {items.map((feature, i) => (
          <li
            key={feature.key}
            className="landing-shot"
            data-active={i === active ? "true" : "false"}
            aria-roledescription="slide"
            aria-label={`${i + 1} of ${count}`}
          >
            <div className="onboarding-phone landing-phone">
              <Image
                src={`/onboarding/onboarding-${feature.key}.webp`}
                alt={`${feature.title} screen, shown with sample league data`}
                width={600}
                height={1298}
                sizes="(min-width: 768px) 160px, 136px"
                priority={i < 2}
                className="onboarding-phone-img landing-shot-img"
              />
            </div>
            <div className="landing-shot-caption">
              <p className="landing-shot-title">{feature.title}</p>
              <p className="landing-shot-benefit">{feature.benefit}</p>
            </div>
          </li>
        ))}
      </ul>
      <div className="landing-showcase-controls">
        <div className="landing-showcase-dots" role="group" aria-label="Choose a screen">
          {items.map((feature, i) => (
            <button
              key={feature.key}
              type="button"
              className="landing-showcase-dot"
              aria-label={`Show ${feature.title}`}
              aria-current={i === active ? "true" : undefined}
              onClick={() => goTo(i)}
            />
          ))}
        </div>
        {!reduced && (
          <button
            type="button"
            className="landing-showcase-pause"
            aria-pressed={userPaused}
            aria-label={userPaused ? "Play slideshow" : "Pause slideshow"}
            onClick={() => setUserPaused((p) => !p)}
          >
            <svg aria-hidden="true" width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
              {userPaused ? <path d="M2 1l7 4-7 4z" /> : <path d="M2 1h2v8H2zM6 1h2v8H6z" />}
            </svg>
          </button>
        )}
      </div>
    </section>
  );
}
