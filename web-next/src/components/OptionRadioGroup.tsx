"use client";

/**
 * A labelled single-choice list: each option is a full-width row with a
 * title, a one-line description and an On/Off state tag. The visual twin of
 * the Account page's "Dynasty experience" picker, for instant (synchronous)
 * settings like density and theme.
 */
export function OptionRadioGroup<T extends string>({
  id,
  label,
  options,
  value,
  onChange,
}: {
  id: string;
  label: string;
  options: Array<{ value: T; label: string; description: string }>;
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span id={id} className="text-sm font-semibold">
        {label}
      </span>
      <div
        role="radiogroup"
        aria-labelledby={id}
        className="flex flex-col"
        style={{ border: "var(--border-width-default) solid var(--color-border)" }}
      >
        {options.map((option, index) => {
          const selected = value === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => {
                if (!selected) onChange(option.value);
              }}
              className="flex items-center justify-between gap-3 p-3 text-left"
              style={{
                borderTop: index === 0 ? "none" : "var(--border-width-default) solid var(--color-border)",
                background: selected ? "var(--color-action-soft)" : "transparent",
              }}
            >
              <span className="flex flex-col gap-0.5">
                <span className="text-sm">{option.label}</span>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {option.description}
                </span>
              </span>
              <span
                className="px-2.5 py-1 text-xs font-bold"
                style={{
                  border: "var(--border-width-default) solid var(--color-border)",
                  color: selected ? "var(--color-success)" : "var(--color-text-muted)",
                }}
              >
                {selected ? "On" : "Off"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
