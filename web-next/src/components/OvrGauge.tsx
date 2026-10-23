import { ValueRing } from "@/components/ValueRing";
import { overallRatingTint } from "@/lib/playerPresentation";

const RING_SIZE = { sm: "xs", md: "sm", lg: "md" } as const;

/**
 * The one "NN OVR" rendering sitewide (coridian_: "the overall ALWAYS needs
 * to be a circular gauge throughout the site", 2026-10-14): a ValueRing tinted
 * by the rating (lib/playerPresentation overallRatingTint). Shows no
 * ring/number when `rating` is null (no fabricated rating for a thin
 * per-position pool) but still reserves the same footprint so the value
 * column of rows without an OVR stays aligned with rows that have one.
 */
export function OvrGauge({ rating, size = "sm" }: { rating: number | null; size?: "sm" | "md" | "lg" }) {
  const ringSize = RING_SIZE[size];
  if (rating === null || rating === undefined) {
    return <span className={`value-ring-placeholder value-ring--${ringSize}`} aria-hidden="true" />;
  }
  const clamped = Math.max(0, Math.min(99, Math.round(rating)));
  return (
    <ValueRing
      percent={clamped}
      tint={overallRatingTint(clamped)}
      display={String(clamped)}
      ariaLabel={`${clamped} overall rating`}
      size={ringSize}
    />
  );
}
