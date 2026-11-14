/**
 * Fantasy Sim "New game" setup: the presentation model for the grouped, glass-card layout (Quick start | Customize).
 * Pure and imports-free apart from simGame, so web and mobile hold a byte-identical copy
 * (scripts/check_lib_twins.mjs). Nothing here touches the create payload: `simSetupBody` in simGame.ts still builds it.
 */
import { SIM_SCORING_LABELS, type SimDifficulty, type SimGlyphName, type SimSetupState } from "./simGame";

export type SimSetupTab = "quick" | "custom";

export const SIM_SETUP_TABS: { key: SimSetupTab; label: string }[] = [
  { key: "quick", label: "Quick start" },
  { key: "custom", label: "Customize" },
];

export type SimSetupCardId = "start" | "difficulty" | "format" | "league" | "extras";

/** Icon (existing SimGlyph names), title and the static one-line job of each card. */
export const SIM_SETUP_CARDS: Record<SimSetupCardId, { title: string; glyph: SimGlyphName; hint: string }> = {
  start: { title: "Start", glyph: "spark", hint: "A new league by default, and your team name." },
  difficulty: { title: "Difficulty", glyph: "hot", hint: "How sharp the AI managers are." },
  format: { title: "Format", glyph: "checklist", hint: "Redraft or dynasty, and how long you play." },
  league: { title: "League", glyph: "league", hint: "Size, scoring, lineup and tiebreaker." },
  extras: { title: "Rosters", glyph: "team", hint: "Bench, draft slot, IR and taxi." },
};

/** One short descriptor card per difficulty level (the blurb is the existing SIM_DIFFICULTY_COPY wording). */
export const SIM_DIFFICULTY_CARDS: Record<SimDifficulty, { tagline: string; detail: string }> = {
  easy: { tagline: "Relaxed", detail: "Looser AI managers: more passive, more trade-friendly, slower on waivers." },
  normal: { tagline: "Balanced", detail: "A mixed league of AI managers. The default." },
  hard: { tagline: "Cutthroat", detail: "Sharper AI managers: tighter trades and smarter waiver moves." },
};

export const SIM_DIFFICULTY_FOOTNOTE = "Your own scoring is the same at every level.";

/** "Standard lineup", "Superflex lineup", "Standard lineup + K + DEF". */
export function simSetupLineupLabel(s: Pick<SimSetupState, "superflex" | "includeK" | "includeDef">): string {
  const base = s.superflex ? "Superflex lineup" : "Standard lineup";
  const extras = [s.includeK ? "K" : "", s.includeDef ? "DEF" : ""].filter(Boolean);
  return extras.length ? `${base} + ${extras.join(" + ")}` : base;
}

function scoringLabel(s: Pick<SimSetupState, "scoring" | "tePremium">): string {
  const base = SIM_SCORING_LABELS[s.scoring] ?? String(s.scoring);
  return s.tePremium > 0 ? `${base}, TE +${s.tePremium}` : base;
}

/** The live "your league" chips, in reading order. A league import takes size, scoring and lineup from the league. */
export function simSetupChips(s: SimSetupState): string[] {
  const chips =
    s.start === "league"
      ? ["Your league", "Its scoring", "Its lineup"]
      : [`${s.teams} teams`, scoringLabel(s), simSetupLineupLabel(s)];
  chips.push(s.mode === "dynasty" ? `Dynasty, ${s.seasons} seasons` : "Redraft");
  return chips;
}

/** One sentence for the quick-start card: "12 teams, half PPR, standard lineup. Redraft, normal AI." */
export function simSetupHeadline(s: SimSetupState): string {
  const lower = (t: string) => t.replace(/^(Half|Standard|Superflex)/, (m) => m.toLowerCase());
  const first =
    s.start === "league"
      ? "Your league's size, scoring and lineup"
      : `${s.teams} teams, ${lower(scoringLabel(s))}, ${lower(simSetupLineupLabel(s))}`;
  const mode = s.mode === "dynasty" ? `Dynasty, up to ${s.seasons} seasons` : "Redraft, one season";
  return `${first}. ${mode}, ${s.difficulty} AI.`;
}

/** The per-card one-line summaries that update as options change. `teamLabel` is the picked team name (fresh) or "". */
export function simSetupCardSummaries(s: SimSetupState, teamLabel = ""): Record<SimSetupCardId, string> {
  const league = s.start === "league";
  const dynasty = s.mode === "dynasty";
  return {
    start: league ? (s.startPoint === "current" ? "From your league, current week" : "From your league") : `New league${teamLabel ? `, ${teamLabel}` : ""}`,
    difficulty: `${s.difficulty.charAt(0).toUpperCase()}${s.difficulty.slice(1)}: ${SIM_DIFFICULTY_CARDS[s.difficulty].tagline.toLowerCase()}`,
    format: dynasty ? `Dynasty, ${s.seasons} seasons, ${s.rookieRounds}-round rookie draft` : "Redraft, one season",
    league: league ? "Set by your league" : `${s.teams} teams, ${scoringLabel(s)}, ${simSetupLineupLabel(s)}`,
    extras: `${s.bench} bench${s.irSlots == null ? "" : `, ${s.irSlots} IR`}${s.taxiSlots == null ? "" : `, ${s.taxiSlots} taxi`}`,
  };
}

/** Customize tab badge: how many options differ from the quick-start defaults. */
export function simSetupChangedLabel(changed: number): string {
  return changed > 0 ? `${changed} changed` : "";
}
