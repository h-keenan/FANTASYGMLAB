/**
 * Small glyph per news/alert event type (injury, transaction, role/depth
 * chart, off-field). Plain inline SVG with `currentColor` strokes, same
 * approach as SnapshotTileGlyph; pairs with eventTypeColorVar for the tint.
 */
export function EventTypeGlyph({ eventType, size = 14 }: { eventType: string | null; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
  switch (eventType) {
    case "injury/status":
      // Medical cross.
      return (
        <svg {...common}>
          <path d="M8 2.5v11M2.5 8h11" />
        </svg>
      );
    case "transaction":
      // Swap arrows.
      return (
        <svg {...common}>
          <path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" />
        </svg>
      );
    case "role/depth chart":
      // Rising bars.
      return (
        <svg {...common}>
          <path d="M3.5 13V9M8 13V6M12.5 13V3" />
        </svg>
      );
    default:
      // Speech bubble (off-field / other).
      return (
        <svg {...common}>
          <path d="M3 3.5h10v7H8.5L5.5 13v-2.5H3z" />
        </svg>
      );
  }
}

/** Event-type pill: glyph + label in the event's semantic tint. */
export function EventTypePill({
  eventType,
  label,
  color,
  testId,
}: {
  eventType: string | null;
  label: string;
  color: string;
  testId?: string;
}) {
  return (
    <span
      data-testid={testId}
      className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-extrabold uppercase whitespace-nowrap"
      style={{
        borderRadius: "var(--radius-pill)",
        background: `color-mix(in srgb, ${color} var(--chip-fill-pct, 15%), transparent)`,
        color: `color-mix(in srgb, ${color} 80%, var(--color-text-primary))`,
        letterSpacing: "var(--letter-spacing-badge)",
      }}
    >
      <EventTypeGlyph eventType={eventType} size={12} />
      {label}
    </span>
  );
}
