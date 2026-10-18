"use client";

import Image from "next/image";
import { useState } from "react";

import { api } from "@/lib/api";
import { BRAND_NAME } from "@/lib/brand";

type ExperienceLevel = "beginner" | "advanced";

/**
 * Signup onboarding carousel — Zach, 2026-10-18: "we need a more
 * onboarding. We need at least 3 pgs on sign up abt who we are and what we
 * solve and how it works and ask if the user is a beginner or advanced."
 * Shown once, right after a brand-new account's first sign-in, before
 * OnboardingPaywall — mirrors mobile's own OnboardingScreen.tsx timing
 * ("shown once after sign-in"), just a focused 4-step version instead of
 * mobile's full 6-slide tutorial (that one also covers the GM orb and
 * Premium, which don't exist as concepts on web yet).
 *
 * Steps 1-3's copy is verbatim from mobile's OnboardingScreen.tsx SLIDES
 * array ("Copy approved by coridian_ via Discord brainstorm, 2026-09-26 —
 * do not rephrase without re-checking with product") — not rewritten here.
 * Step 4 (experience level) is new; the only approved copy for it is this
 * component's own.
 *
 * Deliberately a fixed dark/cinematic treatment regardless of the app's
 * normal light/dark theme toggle (prefers-color-scheme) — this is a
 * one-time, brief intro screen, not a persistent themed surface, and the
 * animated field-line background only reads correctly on black.
 */
export function OnboardingCarousel({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [level, setLevel] = useState<ExperienceLevel | null>(null);
  const [saving, setSaving] = useState(false);

  const totalSteps = 4;

  const finish = async () => {
    if (!level) return;
    setSaving(true);
    try {
      await api.setExperienceLevel(level);
    } catch {
      // Best-effort — a failed preference write should never block
      // onboarding itself; the question can always be answered again
      // later once Settings reads/writes this same field.
    }
    setSaving(false);
    onDone();
  };

  const next = () => {
    if (step === totalSteps - 1) {
      void finish();
      return;
    }
    setStep((s) => s + 1);
  };

  return (
    <div className="onboarding-shell">
      <div className="onboarding-field" aria-hidden="true" />
      <div className="onboarding-sweep" aria-hidden="true" />

      <div className="onboarding-content">
        <div className="onboarding-topbar">
          <div className="onboarding-dots">
            {Array.from({ length: totalSteps }).map((_, i) => (
              <span key={i} className={`onboarding-dot${i === step ? " onboarding-dot--active" : ""}`} />
            ))}
          </div>
          <button type="button" onClick={onDone} className="onboarding-skip">
            Skip
          </button>
        </div>

        {step === 0 ? (
          <div className="onboarding-hero">
            <Image src="/brand-mark-white.png" alt="" width={56} height={56} className="onboarding-mark" />
            <span className="onboarding-eyebrow">Who we are</span>
            <h1 className="onboarding-headline">Your fantasy front office, not just a stats app.</h1>
            <p className="onboarding-body">
              Real recommendations across your Trade Hub, Waivers, and Next Move — not raw data you have to interpret
              yourself.
            </p>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="onboarding-section">
            <span className="onboarding-eyebrow">What we solve</span>
            <h1 className="onboarding-headline onboarding-headline--sm">
              Dynasty data is everywhere.
              <br />
              Decisions are hard.
            </h1>
            <div className="onboarding-cards">
              <div className="onboarding-glass onboarding-row">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-premium)" strokeWidth="2">
                  <path d="M4 8h14M14 4l4 4-4 4M20 16H6M10 12l-4 4 4 4" />
                </svg>
                <div>
                  <div className="onboarding-row-title">Trade Hub</div>
                  <div className="onboarding-row-body">
                    Real, believable trade ideas — ones your league partners would actually say yes to.
                  </div>
                </div>
              </div>
              <div className="onboarding-glass onboarding-row">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="2">
                  <circle cx="12" cy="12" r="8" />
                  <path d="M12 8v8M8 12h8" />
                </svg>
                <div>
                  <div className="onboarding-row-title">Waivers</div>
                  <div className="onboarding-row-body">
                    Priority Adds ranked for your roster, not a generic most-added list.
                  </div>
                </div>
              </div>
              <div className="onboarding-glass onboarding-row">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--color-accent-strong)"
                  strokeWidth="2"
                >
                  <path d="M13 2L4 14h6l-1 8 9-12h-6l1-8z" strokeLinejoin="round" />
                </svg>
                <div>
                  <div className="onboarding-row-title">Next Move</div>
                  <div className="onboarding-row-body">One clear top priority every time you open the app.</div>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="onboarding-section">
            <span className="onboarding-eyebrow">How it works</span>
            <h1 className="onboarding-headline onboarding-headline--sm">Three steps. That&apos;s it.</h1>
            <div className="onboarding-steps">
              <div className="onboarding-step">
                <span className="onboarding-step-n" style={{ background: "var(--color-accent-strong)", color: "#061014" }}>
                  1
                </span>
                <div className="onboarding-glass onboarding-step-card">
                  <div className="onboarding-row-title">Connect your Sleeper league</div>
                  <div className="onboarding-row-body">
                    The one setup step. Every recommendation depends on it.
                  </div>
                </div>
              </div>
              <div className="onboarding-step">
                <span className="onboarding-step-n" style={{ background: "var(--color-premium)", color: "#1a1400" }}>
                  2
                </span>
                <div className="onboarding-glass onboarding-step-card">
                  <div className="onboarding-row-title">Get your Game Plan</div>
                  <div className="onboarding-row-body">
                    The Dashboard leads with your top priority action first.
                  </div>
                </div>
              </div>
              <div className="onboarding-step">
                <span className="onboarding-step-n" style={{ background: "var(--color-success)", color: "#06210f" }}>
                  3
                </span>
                <div className="onboarding-glass onboarding-step-card">
                  <div className="onboarding-row-title">Make your move</div>
                  <div className="onboarding-row-body">
                    Act straight from Trade Hub or Waivers — recommendation and action, same place.
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="onboarding-section onboarding-section--center">
            <span className="onboarding-eyebrow">Last thing</span>
            <h1 className="onboarding-headline onboarding-headline--sm">How much dynasty experience do you have?</h1>
            <p className="onboarding-body onboarding-body--center">
              Tunes how much explanation shows up alongside recommendations. Change it anytime in Settings.
            </p>
            <div className="onboarding-cards" style={{ marginTop: "var(--space-md)" }}>
              <button
                type="button"
                onClick={() => setLevel("beginner")}
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
                onClick={() => setLevel("advanced")}
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
          <button
            type="button"
            onClick={next}
            disabled={(step === totalSteps - 1 && !level) || saving}
            className="onboarding-next"
          >
            {step === totalSteps - 1
              ? saving
                ? `Setting up ${BRAND_NAME}…`
                : "Start my 7-day free trial"
              : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
