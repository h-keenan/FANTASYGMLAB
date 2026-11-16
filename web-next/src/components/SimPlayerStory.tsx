"use client";

import { CompactModule } from "@/components/ui/CompactModule";
import type { SimStoryEntry } from "@/lib/simGame";
import { simStoryGroups, simStorySummaryParts, simStoryToneKey, simStoryWhen } from "@/lib/simStory";

const TONE_COLOR = { success: "var(--color-success)", danger: "var(--color-danger)", muted: "var(--color-text-muted)" } as const;

/**
 * "What is this guy's story?" in a Fantasy Sim player's quick view: a plain-language timeline per season (his depth slot
 * and why he moved, injuries and games missed, trades, big seasons and busts), derived on the server from the game's
 * event log. Collapsed it reads the latest season line; open by default so the answer is on screen. Mobile twin:
 * mobile/src/components/SimPlayerStory.tsx.
 */
export function SimPlayerStory({ story }: { story: readonly SimStoryEntry[] | undefined }) {
  const parts = simStorySummaryParts(story);
  if (parts.length === 0) return null;
  return (
    <CompactModule id="simpqv.story" title="Story" label="Player story" parts={parts} tone="accent" defaultOpen testId="sim-player-story">
      <div className="flex flex-col gap-3">
        {simStoryGroups(story).map((group) => (
          <section key={group.key} aria-label={group.label} className="flex flex-col gap-1">
            <h4 className="text-xs font-extrabold" style={{ color: "var(--color-text-secondary)" }}>{group.label}</h4>
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {group.entries.map((e, i) => (
                <li key={i} className="flex items-baseline gap-2 text-sm" data-testid="sim-story-line" data-kind={e.kind} data-tone={e.tone}>
                  <span className="w-16 shrink-0 text-xs tabular-nums" style={{ color: "var(--color-text-muted)" }}>{simStoryWhen(e)}</span>
                  <span className={e.kind === "season" ? "font-extrabold" : undefined} style={{ color: e.tone === "neutral" ? undefined : TONE_COLOR[simStoryToneKey(e.tone)] }}>{e.text}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </CompactModule>
  );
}
