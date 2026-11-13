"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

const TICK_MS = 450;
const FLASH_MS = 1100;

/**
 * A number that counts to its new value (about 450 ms, ease-out) and flashes
 * green when it goes up. Reduced motion: no counting, the value just
 * changes and the (non-moving) green flash remains. First render never
 * animates. Twin of mobile/src/components/TickNumber.tsx.
 */
export function TickNumber({
  value,
  decimals = 1,
  className,
  style,
  testId,
}: {
  value: number | null | undefined;
  decimals?: number;
  className?: string;
  style?: CSSProperties;
  testId?: string;
}) {
  const target = typeof value === "number" && Number.isFinite(value) ? value : null;
  const [anim, setAnim] = useState<{ target: number; value: number } | null>(null);
  const [flashing, setFlashing] = useState(false);
  const previous = useRef<number | null>(target);

  useEffect(() => {
    const from = previous.current;
    previous.current = target;
    if (target == null || from == null || from === target) return;
    let raf: number | null = null;
    let flashTimer: ReturnType<typeof setTimeout> | null = null;
    const reduced = prefersReducedMotion();
    const start = performance.now();
    const step = (now: number) => {
      const t = reduced ? 1 : Math.min(1, (now - start) / TICK_MS);
      const eased = 1 - (1 - t) ** 3;
      setAnim({ target, value: from + (target - from) * eased });
      if (t === 1 || !(t < 1)) return;
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame((now) => {
      if (target > from) {
        setFlashing(true);
        flashTimer = setTimeout(() => setFlashing(false), FLASH_MS);
      }
      step(now);
    });
    return () => {
      if (raf != null) cancelAnimationFrame(raf);
      if (flashTimer) clearTimeout(flashTimer);
    };
  }, [target]);

  // While a tick is running for this exact target show the in-between value; otherwise the target itself.
  const shown = anim && anim.target === target ? anim.value : target;

  return (
    <span
      data-testid={testId}
      data-flash={flashing ? "up" : undefined}
      className={`tick-number tabular-nums${className ? ` ${className}` : ""}`}
      style={style}
    >
      {shown == null ? "—" : shown.toFixed(decimals)}
    </span>
  );
}
