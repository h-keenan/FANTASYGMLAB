import { injuryTone } from "@/lib/myTeamPresentation";

/**
 * The general injury-status glyph for any compact player card — IR,
 * Questionable, Out, etc. coridian_, 2026-10-18 (screenshot): "we need a
 * status glyph? icon indicator indicating injury status including IR,
 * questionable, pending etc... that can be a general status indicator
 * place for the compact player card." Reuses MyTeamContent.tsx's own
 * injuryTone mapping and badge styling verbatim (its LineupRow already
 * renders this exact text/color pair next to a player's name) rather than
 * inventing a second convention — this just makes it available wherever a
 * compact card shows a player, not only on My Team's full lineup rows.
 * Renders nothing for a healthy/unknown player, never a fabricated status.
 */
export function PlayerInjuryBadge({ status }: { status: string | null | undefined }) {
  const label = (status || "").trim();
  if (!label) return null;
  const tone = injuryTone(label);
  return (
    <span
      className="px-1 text-xs font-bold uppercase shrink-0"
      style={{
        color:
          tone === "danger"
            ? "var(--color-danger)"
            : tone === "warning"
              ? "var(--color-warning)"
              : "var(--color-text-muted)",
      }}
    >
      {label}
    </span>
  );
}
