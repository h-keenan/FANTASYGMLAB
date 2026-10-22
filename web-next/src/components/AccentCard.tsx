import type { CSSProperties, ReactNode, Ref } from "react";

/**
 * The one accent-left-edge card: a glass card with a 3px left rail in a
 * semantic color and the same padding everywhere (`p-4`, `gap-3`). `compact`
 * is the denser `p-3 gap-1` form for short fact cards. `accent` is a CSS
 * color expression (a semantic token, never a raw hex).
 */
export function AccentCard({
  accent,
  compact = false,
  as: Tag = "article",
  className = "",
  style,
  children,
  ref,
  ...rest
}: {
  accent: string;
  compact?: boolean;
  as?: "article" | "section" | "div";
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
  ref?: Ref<HTMLElement>;
  "data-highlighted"?: string;
}) {
  return (
    <Tag
      ref={ref as Ref<HTMLDivElement>}
      className={`glass-surface flex flex-col ${compact ? "gap-1 p-3" : "gap-3 p-4"} ${className}`.trim()}
      style={{ borderLeft: `var(--border-width-semantic) solid ${accent}`, ...style }}
      {...rest}
    >
      {children}
    </Tag>
  );
}
