import { ToneBadge } from "@/components/ToneBadge";

/** The "Pro" lock marker on a paid nav row (GM orb and desktop sidebar).
 * Gold (the one premium token) so it reads as the same thing as every other
 * Pro surface. Render only when the person is known not to be on Pro. */
export function NavProMarker() {
  return <ToneBadge label="Pro" color="var(--color-premium)" size="xs" srLabel="Pro feature" testId="nav-pro-marker" />;
}
