/**
 * Shared "segmented meter" row — ports mobile's MeterRow
 * (components/ConfidenceMeter.tsx), itself extracted there from Trade Hub's
 * own confidence/realism display so the same real-signal-backed badge
 * pattern could be reused wherever another surface has a genuine,
 * already-computed confidence-like signal to show.
 *
 * Waivers is the first web-next surface with its own distinct confidence
 * signal (modules.waivers_ui.waiver_confidence_label's High/Medium/Low,
 * mirrored by GET .../leagues/{id}/waivers' `confidence_label`/
 * `confidence_reason` on every Priority Add) — the UX audit that scoped
 * this page specifically called out its "confidence bars" as a standout.
 * Trade Hub's own confidence/realism signal uses a circular ValueRing
 * instead (see components/ValueRing.tsx) since that's what the real app
 * shows there; this bar-segment visual is what the real app (and mobile)
 * shows for Waivers specifically, so it's ported as its own component
 * rather than forcing one ring primitive to stand in for two different
 * real visual languages.
 */
export function confidenceLevelFor(label: string | null | undefined): number {
  const normalized = (label ?? "").trim().toLowerCase();
  if (normalized === "high") return 3;
  if (normalized === "medium") return 2;
  return 1;
}

export function ConfidenceMeter({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  const level = confidenceLevelFor(value);
  return (
    <div className="flex items-center gap-1.5" role="img" aria-label={`${label}: ${value}`}>
      <span
        className="text-xs font-bold uppercase"
        style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        {label}
      </span>
      <span className="flex items-center gap-0.5" aria-hidden="true">
        {[1, 2, 3].map((segment) => (
          <span
            key={segment}
            style={{
              width: 14,
              height: 4,
              borderRadius: 2,
              background: segment <= level ? color : "var(--color-border)",
            }}
          />
        ))}
      </span>
      <span className="text-xs font-bold" style={{ color }}>
        {value}
      </span>
    </div>
  );
}
