"use client";

import { ButtonLink } from "@/components/Button";
import { nextStepHref, type NextStepKey } from "@/components/NextSteps";
import { useDefaultLeague } from "@/lib/useDefaultLeague";

/**
 * A single next-step link from a page that has no league of its own (News,
 * Trade History, Community) into a league page: straight to the account's
 * only league, or to the Portfolio to pick one when there are several.
 * Renders nothing until the account's leagues are known, or with none.
 */
export function LeagueLinkStep({
  step,
  label,
  pickLabel = "Pick a league",
  variant = "secondary",
}: {
  step: NextStepKey;
  label: string;
  pickLabel?: string;
  variant?: "primary" | "secondary";
}) {
  const league = useDefaultLeague();
  if (!league || league.count === 0) return null;
  const href = league.only ? nextStepHref(step, league.only.leagueId, league.only.leagueName) : "/portfolio";
  return (
    <ButtonLink variant={variant} size="sm" href={href} data-testid="league-link-step">
      {league.only ? `${label} →` : `${pickLabel} →`}
    </ButtonLink>
  );
}
