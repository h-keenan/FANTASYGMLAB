import { ButtonLink } from "@/components/Button";
import { SectionHeading } from "@/components/SectionHeading";

/**
 * "What to do next" link row for screens that otherwise end in a dead end
 * (Alerts, Matchup). Each step is a real league page; the label says what
 * the user gets there, not just the page name. Shared with the app's
 * NextSteps (mobile/src/components/NextSteps.tsx): keep the step list and
 * copy identical.
 */
export type NextStepKey = "matchup" | "waivers" | "trade-hub" | "my-team";

const STEPS: Record<NextStepKey, { label: string; segment: string }> = {
  matchup: { label: "Check your lineup", segment: "matchup" },
  waivers: { label: "Find a waiver add", segment: "waivers" },
  "trade-hub": { label: "See trade ideas", segment: "trade-hub" },
  "my-team": { label: "Review your roster", segment: "my-team" },
};

export function nextStepHref(step: NextStepKey, leagueId: string, leagueName: string): string {
  return `/${STEPS[step].segment}/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`;
}

export function NextSteps({
  title = "What to do next",
  steps,
  leagueId,
  leagueName,
}: {
  title?: string;
  steps: NextStepKey[];
  leagueId: string;
  leagueName: string;
}) {
  if (!leagueId) return null;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="next-steps-title" data-testid="next-steps">
      <SectionHeading id="next-steps-title">{title}</SectionHeading>
      <div className="flex flex-wrap gap-2">
        {steps.map((step) => (
          <ButtonLink key={step} variant="secondary" size="sm" href={nextStepHref(step, leagueId, leagueName)}>
            {STEPS[step].label} →
          </ButtonLink>
        ))}
      </div>
    </section>
  );
}
