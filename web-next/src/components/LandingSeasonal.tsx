import { TrackedCtaLink } from "@/components/TrackedCtaLink";
import { seasonalLanding, seasonMoment, withUtm } from "@/lib/seasonalLanding";

/**
 * "What matters this week" strip under the landing hero: one season-aware line, one link to the
 * timely public page, and a no-account Fantasy Sim quickstart. Server component driven by the
 * calendar clock (lib/seasonalLanding.ts); the page revalidates hourly so it follows the season.
 * Same .onboarding-glass surface as the rest of the landing page; the h1 is untouched.
 */
export function LandingSeasonal({ now = new Date() }: { now?: Date }) {
  const copy = seasonalLanding(seasonMoment(now));
  const campaign = `landing_${copy.stage}`;
  return (
    <section
      aria-labelledby="lp-seasonal-heading"
      className="onboarding-glass lp-marketing w-full flex flex-col gap-2 p-4"
      data-testid="landing-seasonal"
      data-stage={copy.stage}
    >
      <p className="text-xs font-bold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "0.03em" }}>
        {copy.eyebrow}
      </p>
      <h2 id="lp-seasonal-heading" className="lp-h3">
        {copy.headline}
      </h2>
      <p className="lp-body">{copy.body}</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <TrackedCtaLink
          href={withUtm(copy.primary.href, "landing", "seasonal", copy.stage)}
          surface={campaign}
          destination="seasonal_primary"
          variant="secondary"
          fullWidth
        >
          {copy.primary.label}
        </TrackedCtaLink>
        <TrackedCtaLink
          href={withUtm(copy.secondary.href, "landing", "seasonal", copy.stage)}
          surface={campaign}
          destination="fantasy_sim_quickstart"
          variant="secondary"
          fullWidth
        >
          {copy.secondary.label}
        </TrackedCtaLink>
      </div>
      <p className="lp-note">No account or league needed for the sample league or Fantasy Sim.</p>
    </section>
  );
}
