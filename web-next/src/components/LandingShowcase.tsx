import Image from "next/image";

import { ONBOARDING_FEATURES } from "@/lib/onboardingFeatures";

/** The real screens worth leading with, in order. Same screenshots and
 *  benefit lines as the signup carousel (lib/onboardingFeatures.ts). */
const SHOWCASE_KEYS = ["gameplan", "tradehub", "matchup", "pqv", "playoff", "waivers"] as const;

/**
 * Landing-page product strip: real screenshots (sample league data) in phone
 * frames, one benefit line under each. A plain CSS scroll-snap row, so it is
 * swipeable on touch with no JS and renders fully on the server. Images have
 * intrinsic width/height (no layout shift); only the first two load eagerly.
 */
export function LandingShowcase() {
  const items = SHOWCASE_KEYS.map((key) => ONBOARDING_FEATURES.find((f) => f.key === key)!);
  return (
    <section aria-label="What FantasyDesk looks like" className="landing-showcase">
      <ul className="landing-showcase-track">
        {items.map((feature, i) => (
          <li key={feature.key} className="landing-shot">
            <div className="onboarding-phone landing-phone">
              <Image
                src={`/onboarding/onboarding-${feature.key}.webp`}
                alt={`${feature.title} screen, shown with sample league data`}
                width={600}
                height={1298}
                sizes="(min-width: 768px) 160px, 136px"
                priority={i < 2}
                className="onboarding-phone-img"
              />
            </div>
            <p className="landing-shot-title">{feature.title}</p>
            <p className="landing-shot-benefit">{feature.benefit}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
