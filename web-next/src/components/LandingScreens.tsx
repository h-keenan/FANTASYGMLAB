import Image from "next/image";

import { ONBOARDING_FEATURES } from "@/lib/onboardingFeatures";

/** The screens worth showing, in order. Same real captures (sample league data)
 *  and benefit lines as the signup carousel. */
const SCREEN_KEYS = ["tradehub", "gameplan", "matchup", "waivers"] as const;

/**
 * Large product screenshots in device frames. A server component: a
 * scroll-snap row (swipeable on phones, a plain row on desktop) with no
 * client JS or autoplay. Every image is lazy-loaded (below the fold), sized
 * for its rendered width so the 600px captures stay sharp on 2x screens.
 */
export function LandingScreens() {
  const items = SCREEN_KEYS.map((key) => ONBOARDING_FEATURES.find((f) => f.key === key)!);
  return (
    <section aria-labelledby="lp-screens-heading" className="lp-section">
      <h2 id="lp-screens-heading" className="lp-h2">
        See it in action
      </h2>
      <p className="lp-lede">Real screens, shown with a sample league.</p>
      <ul className="lp-screens">
        {items.map((feature) => (
          <li key={feature.key} className="lp-screen">
            <div className="lp-device">
              <Image
                src={`/onboarding/onboarding-${feature.key}.webp`}
                alt={`${feature.title} screen, shown with sample league data`}
                width={600}
                height={1298}
                sizes="(min-width: 768px) 240px, 70vw"
                loading="lazy"
                className="lp-device-img"
              />
            </div>
            <p className="lp-screen-title">{feature.title}</p>
            <p className="lp-screen-benefit">{feature.benefit}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
