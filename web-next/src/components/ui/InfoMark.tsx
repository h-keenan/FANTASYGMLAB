"use client";

import { useState, type ReactNode } from "react";

import { ShowExplanationsLink } from "@/components/ShowExplanationsLink";
import { Sheet } from "@/components/ui/Sheet";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { trackUse } from "@/lib/analytics";
import { GLOSSARY, type GlossaryKey } from "@/lib/glossary";
import { whyEntry, type WhyMetricId } from "@/lib/tapForWhyContent";

import "./ui.css";

export type InfoMarkLegendItem = { label: string; color: string; description: string };

export type InfoMarkProps = {
  /** REQUIRED name of what the "?" explains ("this matchup", "Roster Power"). Accessible name is "About <label>"; it is also the sheet heading unless `title` is set. */
  label: string;
  /** Sheet heading when it should differ from `label`. */
  title?: string;
  /** Plain sentences (nullish entries are dropped). */
  lines?: ReadonlyArray<string | null | undefined>;
  /** Registry entries (lib/tapForWhyContent.ts) listed as "<title>: sentences", one block per metric. */
  metrics?: readonly WhyMetricId[];
  /** Glossary terms (lib/glossary.ts) listed as definitions. */
  glossary?: readonly GlossaryKey[];
  /** Coloured term/definition rows (impact tags and the like). */
  legend?: readonly InfoMarkLegendItem[];
  /** Free-form body, rendered after the structured content. */
  children?: ReactNode;
  /** Render only for accounts that show beginner help (experience level), still through this same "?". */
  beginnerOnly?: boolean;
  className?: string;
  testId?: string;
};

/**
 * THE "?" (UI audit batch A, coridian_ 2026-11-16: the old "?" variants "are adding too much space ... and creating their own rows").
 * One component, one placement rule:
 *
 * - Inline, directly after the label or heading it explains (SectionHeading `help`, a tile/card label, PageTitle `info`).
 *   Never its own row, never absolutely positioned over text, never at a row's far edge.
 * - Glyph-sized (18px box), with a 44px hit area made from an expanded ::after so the layout does not grow.
 * - At most one per module: a module that explains several terms passes them all (`lines`, `metrics`, `glossary`, `legend`)
 *   and gets ONE sheet. Copy lives in the shared registries (tapForWhyContent, glossary, experienceCopy), never here.
 *
 * Retired: WhyCorner, InfoTip, GlossaryNote, BeginnerHelp (rows and popovers). scripts/check_info_mark_usage.mjs keeps them gone.
 */
export function InfoMark({ label, title, lines, metrics, glossary, legend, children, beginnerOnly = false, className = "", testId }: InfoMarkProps) {
  const [open, setOpen] = useState(false);
  const copy = useExperienceCopy();
  if (beginnerOnly && !copy.showsHelp) return null;
  const sentences = (lines ?? []).filter((line): line is string => Boolean(line));
  const hasContent = sentences.length > 0 || (metrics?.length ?? 0) > 0 || (glossary?.length ?? 0) > 0 || (legend?.length ?? 0) > 0 || children != null;
  if (!hasContent) return null;
  const multiBlock = (metrics?.length ?? 0) + (glossary?.length ?? 0) + (legend?.length ?? 0) > 1;
  return (
    <>
      <button
        type="button"
        className={`ui-info-mark ${className}`.trim()}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`About ${label}`}
        data-info-mark="true"
        data-testid={testId ?? "info-mark"}
        onClick={() => {
          setOpen(true);
          trackUse("info_mark", "opened");
        }}
      >
        <span aria-hidden="true">?</span>
      </button>
      <Sheet open={open} onClose={() => setOpen(false)} title={title ?? label} size="sm" testId={testId ? `${testId}-sheet` : undefined}>
        <div className="ui-why-body">
          {sentences.map((line) => (
            <p key={line} className="ui-why-sentence">
              {line}
            </p>
          ))}
          {(metrics ?? []).map((id) => {
            const entry = whyEntry(id);
            return (
              <div key={id} className="ui-info-term">
                {multiBlock || sentences.length > 0 ? <p className="ui-info-term-title">{entry.title}</p> : null}
                {entry.sentences.map((sentence) => (
                  <p key={sentence} className="ui-why-sentence">
                    {sentence}
                  </p>
                ))}
              </div>
            );
          })}
          {(glossary ?? []).map((key) => (
            <div key={key} className="ui-info-term">
              <p className="ui-info-term-title">{GLOSSARY[key].label}</p>
              <p className="ui-why-sentence">{GLOSSARY[key].definition}</p>
            </div>
          ))}
          {(legend ?? []).map((item) => (
            <div key={item.label} className="ui-info-term">
              <p className="ui-info-term-title" style={{ color: item.color }}>
                {item.label}
              </p>
              <p className="ui-why-sentence">{item.description}</p>
            </div>
          ))}
          {children != null ? <div className="ui-why-sentence">{children}</div> : null}
          <ShowExplanationsLink />
        </div>
      </Sheet>
    </>
  );
}
