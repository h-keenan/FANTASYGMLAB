"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

import { Sheet } from "@/components/ui/Sheet";
import { trackUse } from "@/lib/analytics";
import { whyEntry, whyTriggerLabel, type WhyMetricId } from "@/lib/tapForWhyContent";

import "./ui.css";

export type TapForWhyProps = {
  /** Registry key (lib/tapForWhyContent.ts). Copy lives there so web and app never disagree. */
  metric: WhyMetricId;
  /** The thing being explained, rendered unchanged: a number, chip, badge, grade, gauge or a whole tile. */
  children: ReactNode;
  /** What a screen reader hears for the trigger: "Why: Value 82". Default: "Why: <entry title>". */
  spoken?: string;
  /**
   * "inline": a number or word inside text (dotted underline on hover/focus).
   * "chip": a badge or pill. "tile": the whole stat tile is the button.
   */
  variant?: "inline" | "chip" | "tile";
  /** Override the sheet heading (default: the registry title). */
  title?: string;
  /** Mini chart or detail shown under the explanation. Rendered only while the sheet is open. */
  chart?: ReactNode;
  /** Extra plain sentences for this instance (for example the engine's own `detail` line), after the registry copy. */
  extra?: readonly string[];
  className?: string;
  testId?: string;
  /** Extra data-* attributes for the trigger button (for example a tone marker styles or tests read). */
  dataAttrs?: Record<`data-${string}`, string>;
};

/**
 * Makes any number, chip, badge or grade tappable. The first thing someone
 * does to learn more about a figure is tap it, so the "why" sits behind the
 * figure itself instead of in a section or a "?" next to it.
 *
 * - Renders a real <button aria-haspopup="dialog"> around the child, with a
 *   44px hit area made from an expanded ::after, so the layout does not grow.
 * - Affordance is quiet: a dotted underline (inline) or a faint ring (chip,
 *   tile) on hover and keyboard focus, and a pressed state. Nothing is added
 *   to the resting look.
 * - Opens a small Sheet: title, 1-3 plain sentences, an optional chart slot,
 *   and a "learn more" link when the registry has one. Fires a
 *   `why_<metric>` usage event.
 */
export function TapForWhy({ metric, children, spoken, variant = "inline", title, chart, extra, className = "", testId, dataAttrs }: TapForWhyProps) {
  const [open, setOpen] = useState(false);
  const entry = whyEntry(metric);
  const sentences = [...entry.sentences, ...(extra ?? [])];
  return (
    <>
      <button
        type="button"
        className={`ui-why ui-why-${variant} ${className}`.trim()}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={whyTriggerLabel(metric, spoken)}
        data-why={metric}
        data-testid={testId}
        {...dataAttrs}
        onClick={() => {
          setOpen(true);
          trackUse(`why_${metric}`, "opened");
        }}
      >
        {children}
      </button>
      <Sheet open={open} onClose={() => setOpen(false)} title={title ?? entry.title} size="sm" testId={testId ? `${testId}-sheet` : undefined}>
        <div className="ui-why-body">
          {sentences.map((sentence) => (
            <p key={sentence} className="ui-why-sentence">
              {sentence}
            </p>
          ))}
          {chart ? <div className="ui-why-chart">{chart}</div> : null}
          {entry.learnMoreHref ? (
            <Link href={entry.learnMoreHref} className="ui-why-learn" onClick={() => setOpen(false)}>
              {entry.learnMoreLabel ?? "Learn more"}
            </Link>
          ) : null}
        </div>
      </Sheet>
    </>
  );
}
