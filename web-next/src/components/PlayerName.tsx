"use client";

import { useLayoutEffect, useRef, useState, type CSSProperties, type ElementType } from "react";

import { PLAYER_NAME_LAST_STAGE, playerNameStage } from "@/lib/playerNameFit";

/**
 * The one way web renders a player name. Owner rule (said five times): when the name does not fit it is the first
 * initial plus the WHOLE surname ("S. Barkley"), never an ellipsis, site-wide. The ladder is `lib/playerNameFit.ts`:
 * full name -> "S. Barkley" -> a font step smaller -> two steps smaller -> wrapped onto two lines. There is no
 * `truncate` / text-overflow anywhere in this component, and callers must not add one (lib/playerNameTruncation.test.ts).
 *
 * Rendering: the full name is rendered first (SSR and hydration agree), then measured before paint in a layout effect;
 * an overflowing stage advances to the next one (state, so React re-measures). The width at which a stage failed is
 * remembered so a later resize that makes room restarts from the full name. No render loop: each stage is tried once
 * per width. Mobile twin: mobile/src/components/PlayerName.tsx. The full name stays in title and the accessible name.
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
  // Width the box had when the current stage was seen overflowing (0 = not overflowing).
  const failedAt = useRef(0);
  // Tie the stage to the name it was measured for so recycled rows restart from the full name.
  const [fit, setFit] = useState<{ name: string; index: number }>({ name: text, index: 0 });
  const index = fit.name === text ? fit.index : 0;
  const stage = playerNameStage(text, index);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => {
      if (stage.wrap) return;
      if (el.scrollWidth > el.clientWidth + 1) {
        failedAt.current = Math.max(failedAt.current, el.clientWidth);
        setFit({ name: text, index: Math.min(PLAYER_NAME_LAST_STAGE, index + 1) });
      }
    };
    check();
    // Web fonts swap in without resizing the box, so re-measure once they load.
    void document.fonts?.ready.then(check);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      // Room appeared since a stage failed: start again from the full name.
      if (index > 0 && failedAt.current > 0 && el.clientWidth > failedAt.current + 1) {
        failedAt.current = 0;
        setFit({ name: text, index: 0 });
      } else check();
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [text, index, stage.wrap]);

  const label = text.trim();
  return (
    <Tag
      ref={ref}
      className={`block min-w-0 max-w-full ${stage.wrap ? "whitespace-normal [overflow-wrap:anywhere] leading-tight" : "whitespace-nowrap"} ${className}`.trim()}
      style={style}
      title={label}
      data-player-name={stage.short ? "short" : "full"}
      data-player-name-stage={stage.index}
    >
      {stage.short && stage.text !== text ? (
        <>
          {/* WCAG 2.5.3 Label in Name: sighted users see the short form, assistive tech reads the full name. */}
          <span aria-hidden="true" style={stage.scale === 1 ? undefined : { fontSize: `${stage.scale}em` }}>{stage.text}</span>
          <span className="sr-only">{text}</span>
        </>
      ) : stage.scale !== 1 ? (
        <span style={{ fontSize: `${stage.scale}em` }}>{text}</span>
      ) : (
        text
      )}
    </Tag>
  );
}
