"use client";

import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import type { BeginnerHelpKey } from "@/lib/experienceCopy";

/**
 * Plain-language helper line for a beginner (onboarding experience level).
 * Renders nothing for advanced or unset accounts, so pages can drop it in
 * next to a term without their own conditional. Pass `term` for a fixed
 * entry from lib/experienceCopy.ts's BEGINNER_HELP, or `text` for a value
 * already resolved through the same copy helpers (e.g. copy.verdictHelp()).
 */
export function BeginnerHelp({
  term,
  text,
  className = "",
}: {
  term?: BeginnerHelpKey;
  text?: string | null;
  className?: string;
}) {
  const copy = useExperienceCopy();
  const resolved = text !== undefined ? (copy.isBeginner ? text : null) : term ? copy.help(term) : null;
  if (!resolved) return null;
  return (
    <p data-beginner-help="true" className={`text-xs ${className}`.trim()} style={{ color: "var(--color-text-muted)" }}>
      {resolved}
    </p>
  );
}
