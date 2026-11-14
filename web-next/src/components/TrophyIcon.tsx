/**
 * The trophy mark (the championship / playoff pages of the recap story). One SVG, colour from `color` (a token such as
 * var(--color-premium)); decorative unless `label` is given. Twin: mobile/src/components/TrophyIcon.tsx.
 */
export function TrophyIcon({ size = 72, color = "var(--color-premium)", label }: { size?: number; color?: string; label?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} data-testid="trophy-icon">
      <path d="M20 8h24v14a12 12 0 0 1-24 0V8Z" fill={color} fillOpacity={0.9} />
      <path d="M20 12H10v4a10 10 0 0 0 10.6 10M44 12h10v4a10 10 0 0 1-10.6 10" stroke={color} strokeWidth={3} strokeLinecap="round" />
      <path d="M32 34v10M24 56h16M26 44h12l2 12H24l2-12Z" stroke={color} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
      <path d="M26 14v8" stroke="#fff" strokeOpacity={0.45} strokeWidth={3} strokeLinecap="round" />
    </svg>
  );
}
