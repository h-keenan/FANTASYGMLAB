import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";

/**
 * The one text input and select: `.glass-input` look, `--radius-control`,
 * 44px minimum height and the global focus ring. `invalid` swaps the border
 * to the danger lane and sets aria-invalid. Label it with a wrapping <label>
 * or aria-label as before; this only owns the control's look.
 */
const controlStyle = (invalid: boolean | undefined) => ({
  minHeight: "var(--control-min-height)",
  color: "var(--color-text-primary)",
  ...(invalid ? { borderColor: "var(--color-danger)" } : {}),
});

export function Input({
  invalid,
  className = "",
  style,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      aria-invalid={invalid || undefined}
      className={`glass-input px-3 text-sm ${className}`.trim()}
      style={{ ...controlStyle(invalid), ...style }}
      {...rest}
    />
  );
}

export function Select({
  invalid,
  className = "",
  style,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select
      aria-invalid={invalid || undefined}
      className={`glass-input px-3 text-sm ${className}`.trim()}
      style={{ ...controlStyle(invalid), ...style }}
      {...rest}
    />
  );
}
