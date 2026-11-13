import { useId, useMemo } from "react";

import { simCrestArt, simCrestLabel, simCrestSpec } from "@/lib/simCrest";

/**
 * A team's generated emblem (shape + pattern + colors + letter, all derived
 * from the team name; lib/simCrest.ts). Original artwork, the same crest on
 * every surface. `label=false` hides it from screen readers when the team
 * name is printed right beside it.
 */
export function SimCrest({ name, size = 28, label = false }: { name: string; size?: number; label?: boolean }) {
  const clipId = useId();
  const spec = useMemo(() => simCrestSpec(name), [name]);
  const art = useMemo(() => simCrestArt(spec), [spec]);
  return (
    <svg
      style={{ width: `calc(${size}px * var(--sim-scale, 1))`, height: `calc(${size}px * var(--sim-scale, 1))` }}
      viewBox={art.viewBox}
      role={label ? "img" : undefined}
      aria-label={label ? simCrestLabel(name) : undefined}
      aria-hidden={label ? undefined : true}
      focusable={false}
      className="shrink-0"
      data-testid="sim-crest"
    >
      <defs>
        <clipPath id={clipId}>
          <path d={art.outline} />
        </clipPath>
      </defs>
      <path d={art.outline} fill={spec.primary} />
      {art.pattern ? (
        <g clipPath={`url(#${clipId})`}>
          <path d={art.pattern} fill={spec.secondary} opacity={0.92} />
        </g>
      ) : null}
      <path d={art.outline} fill="none" stroke={spec.secondary} strokeWidth={3} strokeLinejoin="round" />
      <text x={art.letterX} y={art.letterY} textAnchor="middle" fontSize={art.letterSize} fontWeight={900} fontFamily="system-ui, sans-serif" fill="none" stroke={spec.halo} strokeWidth={4} strokeLinejoin="round" opacity={0.85}>
        {art.letter}
      </text>
      <text x={art.letterX} y={art.letterY} textAnchor="middle" fontSize={art.letterSize} fontWeight={900} fontFamily="system-ui, sans-serif" fill={spec.ink}>
        {art.letter}
      </text>
    </svg>
  );
}
