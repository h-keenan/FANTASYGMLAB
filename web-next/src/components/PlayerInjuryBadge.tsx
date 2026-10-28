import type { CSSProperties, ReactNode } from "react";

import { ToneBadge } from "@/components/ToneBadge";
import { injuryAbbreviation, injuryTone } from "@/lib/myTeamPresentation";

/**
 * The general injury-status glyph for any compact player card — IR,
 * Questionable, Out, etc. coridian_, 2026-10-18 (screenshot): "we need a
 * status glyph? icon indicator indicating injury status including IR,
 * questionable, pending etc... that can be a general status indicator
 * place for the compact player card." Tone comes from myTeamPresentation's
 * injuryTone. Renders nothing for a healthy/unknown player, never a
 * fabricated status.
 *
 * Owner screenshot, 2026-10-21: an inline "QUESTIONABLE" label on the name
 * line squeezed the name down to "Ja...". The badge is now a compact,
 * non-shrinking pill showing a short code (Q, D, O, IR, SUS, ...), with the
 * full status kept as hover text and screen-reader text. Rows place it on
 * their secondary line through `PlayerMetaLine` below, so the name line
 * belongs to the name alone.
 */
export function PlayerInjuryBadge({ status }: { status: string | null | undefined }) {
  const label = (status || "").trim();
  if (!label) return null;
  const tone = injuryTone(label);
  const color =
    tone === "danger"
      ? "var(--color-danger)"
      : tone === "warning"
        ? "var(--color-warning)"
        : tone === "success"
          ? "var(--color-success)"
          : "var(--color-text-muted)";
  return (
    <ToneBadge
      testId="player-injury-badge"
      title={label}
      size="xs"
      color={color}
      label={injuryAbbreviation(label)}
      srLabel={label}
    />
  );
}

/**
 * A player row's secondary line ("MIA · Age 23") with the injury pill
 * beside it. The text wraps, the pill never shrinks, and neither one
 * competes with the name line above for width.
 */
export function PlayerMetaLine({
  injuryStatus,
  children,
  style,
}: {
  injuryStatus: string | null | undefined;
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <span className="flex flex-wrap items-center gap-x-1.5 min-w-0 text-xs">
      <span className="break-words min-w-0" style={{ color: "var(--color-text-muted)", ...style }}>
        {children}
      </span>
      <PlayerInjuryBadge status={injuryStatus} />
    </span>
  );
}
