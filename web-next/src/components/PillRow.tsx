"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

/**
 * The one segmented control / tab bar. Every tab strip in the app is this
 * component; sizing comes from the `--segmented-*` tokens in globals.css.
 *
 * Variants:
 *  - "fill"    equal-width segments across the full row (primary tabs).
 *  - "compact" segments hug their content, no empty bordered area (year /
 *              short toggles). Default.
 *  - "scroll"  full-width single-row strip that scrolls horizontally with
 *              edge fades, never wraps (many / long labels, e.g. filters).
 * Any variant falls back to horizontal scrolling instead of wrapping when
 * its labels overflow. `fullWidth` is kept as an alias for variant="fill".
 *
 * Accessibility: role="tablist", role="tab" + aria-selected, roving tabindex,
 * Arrow/Home/End keys move focus (and select, for button tabs). Options with
 * an `href` render as links so route tabs (Trades) use the same control.
 */
export type PillRowVariant = "fill" | "compact" | "scroll";

export function PillRow({
  options,
  active,
  onSelect,
  fullWidth = false,
  variant,
  ariaLabel,
}: {
  options: { label: string; value: string; href?: string }[];
  active: string;
  onSelect?: (value: string) => void;
  fullWidth?: boolean;
  variant?: PillRowVariant;
  ariaLabel?: string;
}) {
  const mode: PillRowVariant = variant ?? (fullWidth ? "fill" : "compact");
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [fade, setFade] = useState({ left: false, right: false });

  const measure = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const left = el.scrollLeft > 1;
    const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 1;
    setFade((prev) => (prev.left === left && prev.right === right ? prev : { left, right }));
  }, []);

  // Keep the selected tab in view (scrolls only the strip, never the page).
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const selected = el.querySelector<HTMLElement>('[aria-selected="true"]');
    if (selected && el.scrollWidth > el.clientWidth) {
      // Scroll the minimum needed so the selected tab is fully visible.
      const left = selected.offsetLeft;
      const right = left + selected.offsetWidth;
      if (left < el.scrollLeft) el.scrollLeft = left;
      else if (right > el.scrollLeft + el.clientWidth) el.scrollLeft = right - el.clientWidth;
    }
    measure();
  }, [active, options.length, measure]);

  useEffect(() => {
    measure();
    if (typeof ResizeObserver === "undefined" || !scrollerRef.current) return;
    const observer = new ResizeObserver(measure);
    observer.observe(scrollerRef.current);
    return () => observer.disconnect();
  }, [measure]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
    if (!keys.includes(event.key)) return;
    const tabs = Array.from(scrollerRef.current?.querySelectorAll<HTMLElement>('[role="tab"]') ?? []);
    if (tabs.length === 0) return;
    const current = tabs.findIndex((tab) => tab === document.activeElement);
    let next = current < 0 ? 0 : current;
    if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else next = tabs.length - 1;
    event.preventDefault();
    tabs[next].focus();
    const option = options[next];
    if (option && !option.href) onSelect?.(option.value);
  }

  const hasActive = options.some((option) => option.value === active);
  const mask = `linear-gradient(to right, ${fade.left ? "transparent 0, #000 var(--space-xl)" : "#000 0"}, ${
    fade.right ? "#000 calc(100% - var(--space-xl)), transparent 100%" : "#000 100%"
  })`;
  const segment = mode === "fill" ? "flex-1 min-w-0" : mode === "scroll" ? "shrink-0" : "shrink-0";

  return (
    <div
      className={mode === "compact" ? "flex max-w-full self-start" : "flex w-full"}
      style={{ border: "var(--border-width-default) solid var(--color-border)", background: "var(--color-surface-muted)" }}
    >
      <div
        ref={scrollerRef}
        role="tablist"
        aria-label={ariaLabel}
        onKeyDown={onKeyDown}
        onScroll={measure}
        className={`flex min-w-0 overflow-x-auto ${mode === "fill" ? "w-full" : ""}`}
        style={{
          gap: "var(--segmented-gap)",
          scrollbarWidth: "none",
          WebkitMaskImage: fade.left || fade.right ? mask : undefined,
          maskImage: fade.left || fade.right ? mask : undefined,
        }}
      >
        {options.map((option, index) => {
          const isActive = option.value === active;
          const tabbable = isActive || (!hasActive && index === 0);
          const className = `${segment} flex items-center justify-center whitespace-nowrap text-center font-bold uppercase text-[length:var(--segmented-font-size)]`;
          const style = {
            minHeight: "var(--segmented-height)",
            padding: "0 var(--segmented-padding-x)",
            letterSpacing: "var(--letter-spacing-tight)",
            background: isActive ? "var(--color-information-soft)" : "transparent",
            color: isActive ? "var(--color-text-primary)" : "var(--color-text-secondary)",
            boxShadow: isActive ? "inset 0 -2px 0 var(--color-information)" : "none",
            borderLeft: index === 0 ? "none" : "var(--border-width-default) solid var(--color-border)",
          } as const;
          const common = {
            role: "tab" as const,
            "aria-selected": isActive,
            tabIndex: tabbable ? 0 : -1,
            className,
            style,
          };
          const content: ReactNode = option.label;
          if (option.href) {
            return (
              <Link key={option.value} href={option.href} {...common}>
                {content}
              </Link>
            );
          }
          return (
            <button key={option.value} type="button" onClick={() => onSelect?.(option.value)} {...common}>
              {content}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Vertical stack for several tab/filter controls: one shared gap. */
export function TabStack({ children }: { children: ReactNode }) {
  return <div className="flex flex-col" style={{ gap: "var(--segmented-stack-gap)" }}>{children}</div>;
}
