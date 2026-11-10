import { accentFor, type AccentToken } from "@/lib/destinationAccents.generated";

/**
 * A destination's semantic accent as its CSS token, from the one shared map
 * (modules/destination_accents.py, generated into destinationAccents.generated.ts
 * for web and the app). Nav / GM orb rows pass their label, the feature catalog
 * its id; `fallback` covers destinations with no entry (Home, Account, ...).
 */
export function accentVar(idOrLabel: string, fallback: AccentToken = "accent"): string {
  return `var(--color-${accentFor(idOrLabel, fallback)})`;
}
