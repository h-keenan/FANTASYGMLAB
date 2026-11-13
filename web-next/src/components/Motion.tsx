"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { confettiAllowed, confettiPieces, countUpValue, shouldAnimateList, staggerDelay, COUNT_MS } from "@/lib/motion";
import { useInView, useReducedMotion } from "@/lib/useMotion";

/**
 * Entrance for one block: rises in (opacity + a few px, `.motion-in` in globals.css) when it scrolls into view.
 * `index` / `count` stagger a group (the total delay is capped; lists over MAX_ANIMATED_ROWS do not animate at
 * all). Reduced motion or no IntersectionObserver: no animation, content is simply there. Never changes layout.
 */
export function MotionIn({
  children,
  index = 0,
  count = 1,
  className = "",
  style,
  as: Tag = "div",
}: {
  children: ReactNode;
  index?: number;
  count?: number;
  className?: string;
  style?: CSSProperties;
  as?: "div" | "li" | "section" | "span";
}) {
  const ref = useRef<HTMLElement | null>(null);
  const reduced = useReducedMotion();
  const animate = !reduced && shouldAnimateList(count);
  const seen = useInView(ref, animate);
  const delay = staggerDelay(index, count);
  const Component = Tag as "div";
  return (
    <Component
      ref={ref as never}
      className={`${animate ? "motion-in" : ""} ${className}`.trim()}
      data-motion={animate ? (seen ? "in" : "pending") : "off"}
      style={animate ? { ...style, animationDelay: seen ? `${delay}ms` : undefined } : style}
    >
      {children}
    </Component>
  );
}

/**
 * A number that counts up from 0 to `value` the first time it appears (about 450ms, ease-out), then follows
 * changes without recounting. Reduced motion: the final value, no counting. For score and OVR heroes.
 */
export function CountUp({ value, decimals = 1, className, style }: { value: number; decimals?: number; className?: string; style?: CSSProperties }) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(reduced ? value : 0);
  const done = useRef(false);
  useEffect(() => {
    if (reduced || done.current) {
      setShown(value);
      return;
    }
    done.current = true;
    const start = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const t = (now - start) / COUNT_MS;
      setShown(countUpValue(0, value, t));
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, reduced]);
  return (
    <span className={`tabular-nums${className ? ` ${className}` : ""}`} style={style}>
      {shown.toFixed(decimals)}
    </span>
  );
}

/** Confetti burst (transform/opacity pieces, ~1.2s) for a title only; renders nothing otherwise or under reduced motion. */
export function Confetti({ wonTitle }: { wonTitle: boolean }) {
  const reduced = useReducedMotion();
  if (!confettiAllowed({ wonTitle, reduced })) return null;
  return (
    <div className="motion-confetti" aria-hidden="true" data-testid="confetti">
      {confettiPieces().map((p, i) => (
        <span key={i} className="motion-confetti-piece" data-hue={p.hue} style={{ "--x": `${p.x}px`, "--y": `${p.y}px`, "--r": `${p.rotate}deg`, animationDelay: `${p.delay}ms` } as CSSProperties} />
      ))}
    </div>
  );
}

/** Wraps a badge/count: pulses once whenever the count goes up (new item), never on first render. */
export function PulseOnIncrease({ value, children }: { value: number; children: ReactNode }) {
  const previous = useRef(value);
  const [pulse, setPulse] = useState(0);
  useEffect(() => {
    if (value > previous.current) setPulse((n) => n + 1);
    previous.current = value;
  }, [value]);
  return (
    <span key={pulse} className={pulse > 0 ? "motion-pulse" : undefined} data-pulse={pulse > 0 ? "true" : undefined}>
      {children}
    </span>
  );
}
