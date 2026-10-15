function formatRank(rank: number | null, tied: boolean): string {
  if (rank === null || rank === undefined) return "—";
  return tied ? `T-${rank}` : `#${rank}`;
}

export function SnapshotTile({
  label,
  value,
  tone = "neutral",
  note,
}: {
  label: string;
  value: string;
  // "premium" (Revision 14, Draft Center) is the gold highlight for a #1
  // league rank — same --color-premium lane the Teams screen's power-rank
  // trophy treatment uses on mobile, not a new color concept.
  tone?: "neutral" | "risk" | "positive" | "premium";
  /** Optional caption line under the value — e.g. "42 total capital". */
  note?: string;
}) {
  const toneColor =
    tone === "risk"
      ? "var(--color-danger)"
      : tone === "positive"
        ? "var(--color-success)"
        : tone === "premium"
          ? "var(--color-premium)"
          : "var(--color-text-primary)";

  return (
    <div
      className="flex flex-col gap-1 p-3 min-w-[7rem]"
      style={{
        background: "var(--color-surface-secondary)",
        border: `var(--border-width-default) solid ${tone === "premium" ? "var(--color-premium)" : "var(--color-border)"}`,
      }}
    >
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span style={{ font: "var(--type-primary-metric)", color: toneColor }}>{value}</span>
      {note ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {note}
        </span>
      ) : null}
    </div>
  );
}

export { formatRank };
