"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { confettiAllowed, confettiPieces, countUpValue, progressScale, rankChange, shouldAnimateList, staggerDelay, COUNT_MS, RANK_CHIP_MS } from "@/lib/motion";
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

/**
 * THE progress fill: a bar that grows to `percent` (0-100) when it appears and follows changes, on the compositor
 * (`transform: scaleX`, never `width`). Put it inside a track that is `overflow: hidden` with the radius (every bar here
 * already is); it fills the track's height. Reduced motion: the final width at once. Twin: mobile ProgressFill.
 */
export function ProgressFill({ percent, color, className = "", style, testId }: { percent: number | null | undefined; color: string; className?: string; style?: CSSProperties; testId?: string }) {
  const reduced = useReducedMotion();
  const target = progressScale(percent);
  const [shown, setShown] = useState(reduced ? target : 0);
  useEffect(() => {
    // One frame at 0 so the first paint has something to grow from.
    const raf = requestAnimationFrame(() => setShown(target));
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return (
    <div
      className={`progress-fill ${className}`.trim()}
      data-testid={testId}
      data-progress={Math.round(target * 100)}
      style={{ height: "100%", width: "100%", background: color, transform: `scaleX(${reduced ? target : shown})`, ...style }}
    />
  );
}

/** "Up 2" / "down 1" chip that appears when a rank improves or slips and fades after a couple of seconds (never on first render). */
export function RankChip({ rank }: { rank: number | null | undefined }) {
  const previous = useRef(rank);
  const [chip, setChip] = useState<{ dir: "up" | "down"; by: number } | null>(null);
  useEffect(() => {
    const change = rankChange(previous.current, rank);
    previous.current = rank;
    if (!change) return;
    setChip(change);
    const timer = setTimeout(() => setChip(null), RANK_CHIP_MS);
    return () => clearTimeout(timer);
  }, [rank]);
  if (!chip) return null;
  return (
    <span className="rank-chip" data-dir={chip.dir} role="status" aria-label={`${chip.dir === "up" ? "Up" : "Down"} ${chip.by}`}>
      <span aria-hidden="true">{chip.dir === "up" ? "▲" : "▼"}{chip.by}</span>
    </span>
  );
}

/** A check that draws itself inside a soft ring: the success confirmation (a claim landed, a trade was accepted). Static under reduced motion. */
export function SuccessCheck({ size = 28, label = "Done" }: { size?: number; label?: string }) {
  return (
    <span className="success-check" role="img" aria-label={label} style={{ width: size, height: size }}>
      <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" className="success-check-ring" />
        <path d="M7 12.5l3.2 3.2L17 9" className="success-check-mark" pathLength={1} />
      </svg>
    </span>
  );
}
