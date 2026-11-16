"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";

import { COUNT_MS as TICK_MS, FLASH_MS, acquireTween, flashDirection } from "@/lib/motion";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}


/**
 * A number that counts to its new value (about 450 ms, ease-out) and flashes
 * green when it goes up and red when it goes down. Reduced motion: no counting, the value just
 * changes and the (non-moving) green flash remains. First render never
 * animates. Twin of mobile/src/components/TickNumber.tsx.
 */
export function TickNumber({
  value,
  decimals = 1,
  format,
  className,
  style,
  testId,
}: {
  value: number | null | undefined;
  decimals?: number;
  /** Formats the shown (in-between) value instead of `toFixed(decimals)` (money, signed gains). Round inside it. */
  format?: (n: number) => string;
  className?: string;
  style?: CSSProperties;
  testId?: string;
}) {
  const target = typeof value === "number" && Number.isFinite(value) ? value : null;
  const [anim, setAnim] = useState<{ target: number; value: number } | null>(null);
  const [flashing, setFlashing] = useState<"up" | "down" | null>(null);
  const previous = useRef<number | null>(target);

  useEffect(() => {
    const from = previous.current;
    previous.current = target;
    if (target == null || from == null || from === target) return;
    let raf: number | null = null;
    let flashTimer: ReturnType<typeof setTimeout> | null = null;
    // At most MAX_CONCURRENT_TWEENS number tweens run at once; past that the value just changes (the flash still plays).
    const release = acquireTween();
    const reduced = prefersReducedMotion() || release === null;
    const start = performance.now();
    const step = (now: number) => {
      const t = reduced ? 1 : Math.min(1, (now - start) / TICK_MS);
      const eased = 1 - (1 - t) ** 3;
      setAnim({ target, value: from + (target - from) * eased });
      if (t === 1 || !(t < 1)) {
        release?.();
        return;
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame((now) => {
      const dir = flashDirection(from, target);
      if (dir) {
        setFlashing(dir);
        flashTimer = setTimeout(() => setFlashing(null), FLASH_MS);
      }
      step(now);
    });
    return () => {
      if (raf != null) cancelAnimationFrame(raf);
      release?.();
      if (flashTimer) clearTimeout(flashTimer);
    };
  }, [target]);

  // While a tick is running for this exact target show the in-between value; otherwise the target itself.
  const shown = anim && anim.target === target ? anim.value : target;

  return (
    <span
      data-testid={testId}
      data-flash={flashing ?? undefined}
      className={`tick-number tabular-nums${className ? ` ${className}` : ""}`}
      style={style}
    >
      {shown == null ? "—" : format ? format(shown) : shown.toFixed(decimals)}
    </span>
  );
}
