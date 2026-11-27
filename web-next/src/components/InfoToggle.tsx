"use client";

/**
 * The small "i" button that opens/closes a help panel. Help copy lives behind this icon instead of in paragraphs above the
 * field. Mobile twin: InfoToggle in mobile/src/components/InfoToggle.tsx.
 */
export function InfoToggle({ open, onToggle, label }: { open: boolean; onToggle: () => void; label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-expanded={open}
      onClick={onToggle}
      className="flex shrink-0 items-center justify-center font-extrabold"
      style={{
        width: "var(--touch-target-min)",
        height: "var(--touch-target-min)",
        color: open ? "var(--color-accent)" : "var(--color-text-secondary)",
        background: "none",
        border: 0,
        cursor: "pointer",
      }}
    >
      <span
        aria-hidden="true"
        className="flex items-center justify-center text-xs"
        style={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          border: `1px solid ${open ? "var(--color-accent)" : "var(--color-border)"}`,
          fontStyle: "italic",
          fontFamily: "serif",
        }}
      >
        i
      </span>
    </button>
  );
}
