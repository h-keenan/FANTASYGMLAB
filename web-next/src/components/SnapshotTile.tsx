function formatRank(rank: number | null, tied: boolean): string {
  if (rank === null || rank === undefined) return "—";
  return tied ? `T-${rank}` : `#${rank}`;
}

export function SnapshotTile({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "risk" | "positive" }) {
  const toneColor =
    tone === "risk" ? "var(--color-danger)" : tone === "positive" ? "var(--color-success)" : "var(--color-text-primary)";

  return (
    <div
      className="flex flex-col gap-1 p-3 min-w-[7rem]"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
      }}
    >
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      <span style={{ font: "var(--type-primary-metric)", color: toneColor }}>{value}</span>
    </div>
  );
}

export { formatRank };
