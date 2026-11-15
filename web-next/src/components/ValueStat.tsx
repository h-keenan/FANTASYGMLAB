/**
 * A trade/dynasty value number with its small "Value" caption above it
 * (owner decision: the label is small, above the number, everywhere).
 * `label` can be swapped for another caption that follows the same stack.
 */
export function ValueStat({
  value,
  label = "Value",
  align = "right",
  children,
}: {
  value: string | number | null | undefined;
  label?: string;
  align?: "left" | "center" | "right";
  /** Replaces the number (e.g. a tappable score button). */
  children?: React.ReactNode;
}) {
  if (!children && (value === null || value === undefined || value === "")) return null;
  return (
    <span className={`flex flex-col shrink-0 ${align === "right" ? "items-end" : align === "center" ? "items-center" : "items-start"}`} data-testid="value-stat">
      <span
        className="uppercase font-bold"
        style={{ font: "var(--type-supporting-metadata)", color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        {label}
      </span>
      {children ?? (
        <span className="text-sm font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {typeof value === "number" ? Math.round(value).toLocaleString() : value}
        </span>
      )}
    </span>
  );
}
