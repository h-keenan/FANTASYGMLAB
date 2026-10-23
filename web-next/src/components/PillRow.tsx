import Link from "next/link";

/**
 * The one segmented control / tab bar. Compact (wrapping) by default;
 * `fullWidth` stretches equal-width tabs. Options with an `href` render as
 * links (role="tab") so route tabs (Trades) use the same control. Tight
 * tracking, 44px targets.
 */
export function PillRow({
  options,
  active,
  onSelect,
  fullWidth = false,
  ariaLabel,
}: {
  options: { label: string; value: string; href?: string }[];
  active: string;
  onSelect?: (value: string) => void;
  fullWidth?: boolean;
  ariaLabel?: string;
}) {
  const routed = options.some((option) => option.href);
  return (
    <div
      role={routed ? "tablist" : undefined}
      aria-label={routed ? ariaLabel : undefined}
      className={fullWidth ? "flex w-full" : "flex flex-wrap gap-0"}
      style={{ border: "var(--border-width-default) solid var(--color-border)" }}
    >
      {options.map((option, index) => {
        const isActive = option.value === active;
        const className = fullWidth
          ? "flex-1 min-w-0 px-1 min-h-[var(--touch-target-min)] py-3 text-center text-[0.6875rem] sm:text-xs font-bold uppercase"
          : "px-3 min-h-[var(--touch-target-min)] py-3 text-xs font-bold uppercase";
        const style = {
          letterSpacing: "var(--letter-spacing-tight)",
          background: isActive ? "var(--color-information-soft)" : "var(--color-surface-muted)",
          color: isActive ? "var(--color-text-primary)" : "var(--color-text-secondary)",
          boxShadow: isActive ? "inset 0 -2px 0 var(--color-information)" : "none",
          border: "var(--border-width-default) solid var(--color-border)",
          marginLeft: fullWidth && index === 0 ? 0 : "-1px",
        } as const;
        if (option.href) {
          return (
            <Link
              key={option.value}
              href={option.href}
              role="tab"
              aria-selected={isActive}
              className={`${className} flex items-center justify-center`}
              style={style}
            >
              {option.label}
            </Link>
          );
        }
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onSelect?.(option.value)}
            aria-pressed={isActive}
            className={className}
            style={style}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
