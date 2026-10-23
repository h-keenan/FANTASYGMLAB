/**
 * The one switch: a 44px-tall button with `role="switch"`, a track + thumb
 * and an optional visible state word ("On", "Opted out") that stays part of
 * the accessible name. `tone="danger"` colors the on state with the danger
 * lane (opt-outs); the default is the accent. Pass `label` only when the
 * visible text does not already name the control.
 */
export function Toggle({
  checked,
  onChange,
  disabled = false,
  label,
  stateLabel,
  tone = "accent",
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
  stateLabel?: string;
  tone?: "accent" | "danger";
}) {
  const onColor = tone === "danger" ? "var(--color-danger)" : "var(--color-accent-strong)";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="inline-flex shrink-0 items-center gap-2 text-xs font-bold"
      style={{
        minHeight: "var(--touch-target-min)",
        color: checked && tone === "danger" ? "var(--color-danger)" : "var(--color-text-secondary)",
        opacity: disabled ? "var(--opacity-disabled)" : 1,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      {stateLabel ? <span>{stateLabel}</span> : null}
      <span
        aria-hidden="true"
        className="relative inline-block"
        style={{
          width: 44,
          height: 26,
          borderRadius: "var(--radius-pill)",
          background: checked ? onColor : "var(--color-surface-muted)",
          border: "var(--border-width-default) solid var(--color-border-strong)",
          transition: "background 120ms",
        }}
      >
        <span
          className="absolute"
          style={{
            top: 2,
            left: checked ? 20 : 2,
            width: 20,
            height: 20,
            borderRadius: "var(--radius-pill)",
            background: checked ? "var(--color-on-accent)" : "var(--color-text-secondary)",
            transition: "left 120ms",
          }}
        />
      </span>
    </button>
  );
}
