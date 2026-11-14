/**
 * Fantasy Sim hub: the "New game" presets sheet and the first-timer / returning layout states.
 * Pure and byte-identical in web and mobile (scripts/check_lib_twins.mjs). A preset is only a starting point over the
 * existing setup state: `simSetupBody` still builds the create payload and "Customize everything" opens the full setup
 * form seeded with the preset, so no setup option is lost.
 */
import { simSetupDefaults, simSetupModes, type SimGameLite, type SimGameOptionsResponse, type SimSetupState } from "./simGame";
import { simSetupChips } from "./simSetupView";

export type SimPresetId = "quick" | "standard" | "deep";

export interface SimPreset {
  id: SimPresetId;
  /** Pill label. */
  label: string;
  /** One sentence under the pills. */
  blurb: string;
  /** Primary button text, e.g. "Start Quick game". */
  action: string;
  /** The setup the preset starts from (every field present, ready for `simSetupBody`). */
  state: SimSetupState;
}

/** The dynasty season counts the options allow, smallest first. */
function seasonValues(options: SimGameOptionsResponse | null | undefined): number[] {
  const values = options?.options?.seasons?.values ?? [];
  return [...values].filter((n) => Number.isFinite(n) && n > 0).sort((a, b) => a - b);
}

/**
 * The presets this account can start right now. Quick (one redraft season, every default) is always there; the two
 * dynasty presets only appear when the options say dynasty is playable.
 */
export function simHubPresets(options: SimGameOptionsResponse | null | undefined): SimPreset[] {
  const base = simSetupDefaults(options);
  const quick: SimPreset = {
    id: "quick",
    label: "Quick",
    blurb: "One redraft season: draft, the regular season and the playoffs, then your grade.",
    action: "Start Quick game",
    state: { ...base, mode: "redraft" },
  };
  const dynasty = simSetupModes(options).some((m) => m.value === "dynasty");
  if (!dynasty) return [quick];
  const counts = seasonValues(options);
  const short = counts.find((n) => n >= 2) ?? counts[0] ?? 2;
  const long = base.seasons >= 3 ? base.seasons : (counts[counts.length - 1] ?? 5);
  return [
    quick,
    {
      id: "standard",
      label: "Standard",
      blurb: `Dynasty, ${short} seasons, with a rookie draft and offseason between them.`,
      action: "Start Standard game",
      state: { ...base, mode: "dynasty", seasons: short },
    },
    {
      id: "deep",
      label: "Deep dynasty",
      blurb: `Dynasty, up to ${long} seasons: build a roster that lasts.`,
      action: "Start Deep dynasty game",
      state: { ...base, mode: "dynasty", seasons: long },
    },
  ];
}

/** Chips for the picked preset ("12 teams", "Half PPR", "Standard lineup", "Redraft"), plus the AI level. */
export function simHubPresetChips(preset: SimPreset): string[] {
  const chips = simSetupChips(preset.state).slice(0, 2);
  chips.push(preset.state.mode === "dynasty" ? `Dynasty, ${preset.state.seasons} seasons` : "Redraft");
  chips.push(`${preset.state.difficulty.charAt(0).toUpperCase()}${preset.state.difficulty.slice(1)} AI`);
  return chips;
}

export type SimHubMode = "first" | "returning";

/** Which hub layout to draw: no saves (explainer open, nudge to New game) or returning (saved list first). */
export function simHubMode(gameCount: number): SimHubMode {
  return gameCount <= 0 ? "first" : "returning";
}

/** "Redraft · 12 teams" / "Dynasty · 10 teams": the saved-game title (the list has no team name). */
export function simHubGameName(game: Pick<SimGameLite, "settings">): string {
  const dynasty = game.settings.mode === "dynasty";
  return `${dynasty ? "Dynasty" : "Redraft"} · ${game.settings.teams ?? 12} teams`;
}
