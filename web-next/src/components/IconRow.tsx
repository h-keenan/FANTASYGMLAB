import type { ReactNode } from "react";

export type IconRowIcon = "check" | "alert" | "info" | "arrow" | "clock" | "flag";

const PATHS: Record<IconRowIcon, ReactNode> = {
  check: <path d="M3.5 8.5l3 3 6-7" />,
  alert: <path d="M8 3.5v5M8 11.4v.1" />,
  info: <path d="M8 7.2v4.3M8 4.6v.1" />,
  arrow: <path d="M3.5 8h9M9 4.5L12.5 8 9 11.5" />,
  clock: <path d="M8 4.5V8l2.3 1.5" />,
  flag: <path d="M4 2v12M4 3h7.5l-1.8 2.5L11.5 8H4" />,
};

/**
 * A small tinted icon in a soft round chip, followed by text: the replacement
 * for literal "•" bullets and list-disc lists. `color` is a semantic CSS
 * color expression (never a raw hex).
 */
export function IconRow({
  icon = "arrow",
  color = "var(--color-text-muted)",
  children,
  className = "",
  textClassName = "text-sm",
}: {
  icon?: IconRowIcon;
  color?: string;
  children: ReactNode;
  className?: string;
  textClassName?: string;
}) {
  const ring = icon === "clock" || icon === "alert" || icon === "info";
  return (
    <div className={`flex items-start gap-2 ${className}`.trim()}>
      <span
        aria-hidden="true"
        className="inline-flex shrink-0 items-center justify-center"
        style={{
          width: "1.25rem",
          height: "1.25rem",
          borderRadius: "var(--radius-pill)",
          background: `color-mix(in srgb, ${color} 16%, transparent)`,
          color,
        }}
      >
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          {ring ? <circle cx="8" cy="8" r="6.2" strokeWidth="1.2" opacity="0.35" /> : null}
          {PATHS[icon]}
        </svg>
      </span>
      <span className={`${textClassName} min-w-0 break-words`} style={{ color: "var(--color-text-secondary)", paddingTop: "0.0625rem" }}>
        {children}
      </span>
    </div>
  );
}
