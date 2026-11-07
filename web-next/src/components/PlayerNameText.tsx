"use client";

import { useLayoutEffect, useRef, useState, type CSSProperties, type ElementType } from "react";

import { abbreviatePlayerName, shouldAbbreviatePlayerName } from "@/lib/formatPlayerName";

/**
 * The one way web renders a player name in a space that might be too narrow.
 * coridian_'s rule: when a name is too long it reads "F. Lastname", never a
 * character-truncated ellipsis mid-word. Web twin of
 * mobile/src/components/PlayerNameText.tsx.
 *
 * Primary: the deterministic length threshold (shouldAbbreviatePlayerName),
 * decided on first render. Secondary: a ResizeObserver/scrollWidth check that
 * abbreviates a name which still overflows its container (use
 * `threshold={Infinity}` in wide layouts to rely on this alone). `truncate`
 * stays on as the final backstop. The full name is always exposed through
 * title and aria-label.
 */
export function PlayerNameText({
  name,
  threshold,
  as: Tag = "span",
  className = "",
  style,
}: {
  name: string | null | undefined;
  /** Character count above which the abbreviated form is used. Default 12. */
  threshold?: number;
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
}) {
  const text = name ?? "";
  const ref = useRef<HTMLElement | null>(null);
  const byLength = shouldAbbreviatePlayerName(text, threshold);
  const [overflowName, setOverflowName] = useState<string | null>(null);
  // Tie the measured flag to the name it was measured for, so a recycled row
  // showing a different player re-measures instead of inheriting it.
  const abbreviated = byLength || overflowName === text;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || byLength) return;
    const check = () => {
      if (el.scrollWidth > el.clientWidth + 1) setOverflowName(text);
    };
    check();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  }, [text, byLength]);

  const label = text.trim();
  return (
    <Tag
      ref={ref}
      className={`block min-w-0 max-w-full truncate ${className}`.trim()}
      style={style}
      title={label}
      aria-label={label}
    >
      {abbreviated ? abbreviatePlayerName(text) : text}
    </Tag>
  );
}
