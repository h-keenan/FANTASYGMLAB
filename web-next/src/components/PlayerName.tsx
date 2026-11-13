"use client";

import { useLayoutEffect, useRef, useState, type CSSProperties, type ElementType } from "react";

import { shortPlayerName } from "@/lib/playerNameDisplay";

/**
 * The one way web renders a player name in a row or card where it could be
 * truncated. Owner rule: when the full name does not fit it reads
 * "S. Barkley" (first initial + whole surname, suffix kept); only if that
 * STILL does not fit does the surname ellipsize (CSS `truncate`).
 *
 * Rendering: the full name is always rendered first (so SSR and hydration
 * agree), then measured before paint in a layout effect. A name that
 * overflows its box flips to the short form; the natural width is remembered
 * so a later resize that makes room flips it back. No layout shift (the
 * box keeps its own width, only the text inside changes), no render loop
 * (a flip only happens on a measured transition). Mobile twin:
 * mobile/src/components/PlayerName.tsx. The full name stays in title and
 * aria-label.
 */
export function PlayerName({
  name,
  as: Tag = "span",
  className = "",
  style,
}: {
  name: string | null | undefined;
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
}) {
  const text = name ?? "";
  const ref = useRef<HTMLElement | null>(null);
  // Width the full name needs; set when it was seen overflowing.
  const naturalWidth = useRef(0);
  // Tie the flag to the name it was measured for so recycled rows re-measure.
  const [shortName, setShortName] = useState<string | null>(null);
  const short = shortName === text;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => {
      if (!short) {
        if (el.scrollWidth > el.clientWidth + 1) {
          naturalWidth.current = el.scrollWidth;
          setShortName(text);
        }
      } else if (naturalWidth.current > 0 && naturalWidth.current <= el.clientWidth) {
        setShortName(null);
      }
    };
    check();
    // Web fonts swap in without resizing the box, so re-measure once they load.
    void document.fonts?.ready.then(check);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(check);
    observer.observe(el);
    return () => observer.disconnect();
  }, [text, short]);

  const label = text.trim();
  return (
    <Tag
      ref={ref}
      className={`block min-w-0 max-w-full truncate ${className}`.trim()}
      style={style}
      title={label}
      data-player-name={short ? "short" : "full"}
    >
      {short && shortPlayerName(text) !== text ? (
        <>
          {/* WCAG 2.5.3 Label in Name: sighted users see the short form, assistive tech reads the full name. */}
          <span aria-hidden="true">{shortPlayerName(text)}</span>
          <span className="sr-only">{text}</span>
        </>
      ) : (
        text
      )}
    </Tag>
  );
}
