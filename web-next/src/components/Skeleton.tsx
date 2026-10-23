import type { CSSProperties } from "react";

/**
 * The shared skeleton set (web twin of mobile SkeletonBlock / SkeletonCard /
 * SkeletonRows). Every per-layout skeleton is composed from these so the
 * shimmer, radius and spacing are defined once (`.pqv-skeleton-line` in
 * globals.css). Decorative: callers keep their own sr-only status text.
 */
export function SkeletonBlock({
  width = "100%",
  height = 16,
  radius,
  className = "",
  style,
  ...rest
}: {
  width?: number | string;
  height?: number | string;
  radius?: string;
  className?: string;
  style?: CSSProperties;
  "data-fgl-this-week-trade-pending"?: string;
}) {
  return (
    <div
      aria-hidden="true"
      className={`pqv-skeleton-line ${className}`.trim()}
      style={{ width, height, ...(radius ? { borderRadius: radius } : {}), ...style }}
      {...rest}
    />
  );
}

/** A glass card holding `lines` text-line blocks (last one shorter). */
export function SkeletonCard({ lines = 3, className = "", style }: { lines?: number; className?: string; style?: CSSProperties }) {
  return (
    <div className={`glass-surface flex flex-col gap-3 p-4 ${className}`.trim()} style={style} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <SkeletonBlock key={index} width={index === lines - 1 ? "60%" : "100%"} height={index === 0 ? 18 : 14} />
      ))}
    </div>
  );
}

/** Avatar-left, two-line-right list rows. */
export function SkeletonRows({ count = 5 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="flex items-center gap-3">
          <SkeletonBlock width={40} height={40} radius="var(--radius-pill)" />
          <div className="flex flex-1 flex-col gap-2">
            <SkeletonBlock width="70%" height={14} />
            <SkeletonBlock width="45%" height={11} />
          </div>
        </div>
      ))}
    </div>
  );
}
