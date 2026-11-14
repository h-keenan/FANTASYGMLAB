/**
 * A trade/dynasty value number on a row's right edge: ONE compact line, the number with a tiny unit caption after it
 * ("3,213 value"). It used to be a two-line block with a big uppercase "TRADE VALUE" label above the number, which
 * squeezed the name column ("J. Bris...") and sat next to a chevron. The full label stays available as the accessible
 * name and tooltip. `label` can be swapped for another caption ("Score", "Waiver").
 * Rule: lib/rowAffordance.ts (rule 4).
 */
function unitCaption(label: string): string {
  const text = label.trim();
  if (/^trade value$/i.test(text) || /^value$/i.test(text)) return "value";
  const first = text.split(/\s+/)[0] ?? text;
  return (text.length <= 7 ? text : first).toLowerCase();
}

export function ValueStat({
  value,
  label = "Trade value",
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
  const shown = typeof value === "number" ? Math.round(value).toLocaleString() : value;
  return (
    <span
      className={`inline-flex shrink-0 items-baseline gap-1 whitespace-nowrap ${align === "right" ? "justify-end" : align === "center" ? "justify-center" : "justify-start"}`}
      data-testid="value-stat"
      title={children ? label : `${label} ${shown}`}
    >
      {children ?? (
        <span className="text-sm font-extrabold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
          <span className="sr-only">{label} </span>
          {shown}
        </span>
      )}
      <span aria-hidden="true" className="text-[0.6875rem] font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        {unitCaption(label)}
      </span>
    </span>
  );
}
