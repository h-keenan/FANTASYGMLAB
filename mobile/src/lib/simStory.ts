// Shared (web + mobile twin): presentation of a Fantasy Sim player's story (GET /players/{id}/history `story`).
// The server derives the plain-language lines from the game's event log; this only groups, tags and summarises them.
// Import-free of runtime code (types only), so the mobile twin runs under node:test.

import type { SimStoryEntry } from "./simGame";

/** The story grouped by season, newest first. Inside a season the season's own line leads, then what happened in the order it happened. */
export interface SimStoryGroup {
  key: string;
  label: string;
  entries: SimStoryEntry[];
}

export function simStoryGroups(story: readonly SimStoryEntry[] | null | undefined): SimStoryGroup[] {
  const bySeason = new Map<number, SimStoryEntry[]>();
  for (const e of story ?? []) bySeason.set(e.season, [...(bySeason.get(e.season) ?? []), e]);
  return [...bySeason.keys()]
    .sort((a, b) => b - a)
    .map((season) => {
      const entries = bySeason.get(season)!;
      const head = entries.find((e) => e.kind === "season");
      return {
        key: `s${season}`,
        label: entries[0].season_label || `S${season}`,
        entries: [...(head ? [head] : []), ...entries.filter((e) => e !== head)],
      };
    });
}

/** "Wk 5", "Offseason" or "Season" for a story line's small date tag. */
export function simStoryWhen(e: Pick<SimStoryEntry, "kind" | "week">): string {
  if (e.kind === "season") return "Season";
  return e.week > 0 && e.week < 99 ? `Wk ${e.week}` : "Offseason";
}

export interface SimStoryPart {
  key: string;
  text: string;
  strong?: boolean;
  tone?: "success" | "danger";
}

/** The collapsed Story summary: his latest season line first (role, points or why he did not play), then counts of what moved. */
export function simStorySummaryParts(story: readonly SimStoryEntry[] | null | undefined): SimStoryPart[] {
  const all = story ?? [];
  if (all.length === 0) return [];
  const latest = [...all].reverse().find((e) => e.kind === "season");
  const count = (n: number, one: string, many: string) => (n === 0 ? "" : `${n} ${n === 1 ? one : many}`);
  const parts: SimStoryPart[] = [
    { key: "latest", text: latest?.text ?? "", strong: true, ...(latest?.tone === "good" ? { tone: "success" as const } : latest?.tone === "bad" ? { tone: "danger" as const } : null) },
    { key: "depth", text: count(all.filter((e) => e.kind === "depth").length, "depth chart move", "depth chart moves") },
    { key: "hurt", text: count(all.filter((e) => e.kind === "injury").length, "injury", "injuries") },
  ];
  return parts.filter((p) => p.text);
}

/** The colour token a story line's tone maps to (the shared semantic colours: green good, red bad). */
export function simStoryToneKey(tone: SimStoryEntry["tone"]): "success" | "danger" | "muted" {
  return tone === "good" ? "success" : tone === "bad" ? "danger" : "muted";
}
