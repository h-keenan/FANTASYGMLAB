import { ButtonLink } from "@/components/Button";
import { SectionHeading } from "@/components/SectionHeading";

/**
 * "What to do next" link row for screens that otherwise end in a dead end
 * (Alerts, Matchup). Each step is a real league page; the label says what
 * the user gets there, not just the page name. Shared with the app's
 * NextSteps (mobile/src/components/NextSteps.tsx): keep the step list and
 * copy identical.
 */
export type NextStepKey = "matchup" | "waivers" | "trade-hub" | "trade-finder" | "trade-analyzer" | "my-team" | "alerts" | "gm-plan";

const STEPS: Record<NextStepKey, { label: string; segment: string; hash?: string }> = {
  matchup: { label: "Check your lineup", segment: "matchup" },
  waivers: { label: "Find a waiver add", segment: "waivers" },
  "trade-hub": { label: "See trade ideas", segment: "trade-hub" },
  "trade-analyzer": { label: "Analyze a trade", segment: "trade-analyzer" },
  "trade-finder": { label: "See other packages in Trade Finder", segment: "trade-finder" },
  "my-team": { label: "Review your roster", segment: "my-team" },
  // Alerts is a section of Today (2026-11-16 nav consolidation).
  alerts: { label: "See news on your players", segment: "dashboard", hash: "alerts" },
  "gm-plan": { label: "Open your GM Plan", segment: "gm-plan" },
};

export function nextStepHref(step: NextStepKey, leagueId: string, leagueName: string): string {
  const { segment, hash } = STEPS[step];
  return `/${segment}/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}${hash ? `#${hash}` : ""}`;
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
